import base64
import io
import json
import ssl
import tempfile
import traceback
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from .client import IikoClient, IikoError, PATHS, Response, Transport, mask_card
from .config import ConfigurationError, Connection, read_env_file
from .management.commands.iiko_probe import catalog_summary


ORG = "11111111-1111-4111-8111-111111111111"
CUSTOMER = "22222222-2222-4222-8222-222222222222"
TRACE = "33333333-3333-4333-8333-333333333333"


def token(exp=4600):
    payload = base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode()).decode().rstrip("=")
    return "header." + payload + ".signature"


def auth(exp=4600):
    return Response(200, {"token": token(exp), "correlationId": TRACE})


def connection(name="sheregesh", key="private-api-key"):
    return Connection(name, "private-app-id", "private-client-secret", key)


class ClientTests(SimpleTestCase):
    def test_topup_contract_positive_amount_and_no_retries(self):
        client, transport = self.make_client(auth(), Response(200, {}))
        client.topup_wallet(ORG, CUSTOMER, TRACE, "10000.00", ORG)
        self.assertEqual(transport.post.call_args.args[1], "/api/1/loyalty/iiko/customer/wallet/topup")
        self.assertEqual(transport.post.call_args.args[2], {"organizationId": ORG, "customerId": CUSTOMER,
            "walletId": TRACE, "sum": 10000.0, "comment": "AYS Connect operation " + ORG})
        for amount in ("0", "-1", "NaN", "Infinity", "1.001", True, 1.5):
            client, transport = self.make_client()
            with self.assertRaisesRegex(IikoError, "invalid_topup_amount"):
                client.topup_wallet(ORG, CUSTOMER, TRACE, amount, ORG)
            transport.post.assert_not_called()
        for response in (Response(400, {}), Response(401, {}), Response(500, {}), IikoError("network_unavailable")):
            client, transport = self.make_client(auth(), response)
            with self.assertRaises(IikoError):
                client.topup_wallet(ORG, CUSTOMER, TRACE, "10000", ORG)
            self.assertEqual(transport.post.call_count, 2)

    def test_delete_guest_contract_and_counts(self):
        client, transport = self.make_client(auth(), Response(200, {"total": 1, "deleted": 1, "notFound": 0}))
        client.delete_customer(ORG, CUSTOMER)
        self.assertEqual(transport.post.call_args.args[1], "/api/1/loyalty/iiko/delete_customers")
        self.assertEqual(transport.post.call_args.args[2], {"organizationId": ORG, "customerIds": [CUSTOMER]})
        for body in ({}, {"total": 1, "deleted": 0, "notFound": 1}, {"total": True, "deleted": 1, "notFound": 0}):
            client, transport = self.make_client(auth(), Response(200, body))
            with self.assertRaisesRegex(IikoError, "customer_deletion_not_confirmed"):
                client.delete_customer(ORG, CUSTOMER)
            self.assertEqual(transport.post.call_count, 2)

    def test_write_diagnostics_are_bounded_redacted_and_never_retried(self):
        body = {"errorCode": "CardDenied", "errorDescription": "private-client-secret private-api-key private-app-id 12345 Bearer secret-token\n" + "x" * 2100,
                "customer": {"name": "private"}, "error": {"code": "Denied", "message": "Cannot remove card"}}
        client, transport = self.make_client(auth(), Response(400, body))
        with self.assertRaises(IikoError) as caught:
            client.remove_card(ORG, CUSTOMER, "12345")
        detail = caught.exception.diagnostics
        self.assertEqual(detail["fields"]["errorCode"], "CardDenied")
        self.assertEqual(detail["fields"]["error.message"], "Cannot remove card")
        self.assertEqual(len(detail["fields"]["errorDescription"]), 2000)
        for secret in ["private", "12345", "secret-token"]:
            self.assertNotIn(secret, str(detail))
        self.assertNotIn("CardDenied", str(caught.exception))
        self.assertEqual(transport.post.call_count, 2)

    def test_comment_readback_is_available_in_web_profiles_only(self):
        body = {"id": CUSTOMER, "comment": "Заметка\nСтрока", "cards": [], "categories": [], "walletBalances": []}
        client, _ = self.make_client(auth(), Response(200, body), Response(200, body), Response(200, body))
        self.assertEqual(client.registration(ORG, number="123")["comment"], body["comment"])
        self.assertEqual(client.card(ORG, "123", include_owner=True)["comment"], body["comment"])
        self.assertNotIn("comment", client.card(ORG, "123"))

    def make_client(self, *responses, config=None):
        transport = mock.Mock()
        transport.post.side_effect = responses
        client = IikoClient(config or connection(), transport=transport,
                            clock=mock.Mock(return_value=1000), sleep=mock.Mock())
        return client, transport

    def test_auth_contract_and_reuse(self):
        client, transport = self.make_client(auth(), Response(200, {"organizations": []}))
        first = client.authenticate()
        self.assertFalse(first["cached"])
        self.assertTrue(client.authenticate()["cached"])
        client.organizations()
        self.assertEqual(transport.post.call_count, 2)
        self.assertEqual(transport.post.call_args_list[0].args[1:3], (
            "/api/v2/access_token", {"appId": "private-app-id", "clientSecret": "private-client-secret", "apiKey": "private-api-key"}))
        self.assertEqual(transport.post.call_args.args[3], token())
        self.assertNotIn("token", first)

    def test_refresh_before_jwt_expiration(self):
        client, transport = self.make_client(auth(), auth(8200))
        client.authenticate()
        client._clock.return_value = 4540
        client.authenticate()
        self.assertEqual(transport.post.call_count, 2)
        self.assertEqual(client._token, token(8200))

    def test_invalid_exp_is_safely_rejected(self):
        for value in (None, True, "secret", float("nan"), 1000):
            client, _ = self.make_client(auth(value))
            with self.subTest(value=value), self.assertRaisesRegex(IikoError, "invalid_token_response"):
                client.authenticate()

    def test_401_refresh_is_bounded(self):
        client, transport = self.make_client(auth(), Response(401, {}), auth(), Response(401, {}))
        with self.assertRaisesRegex(IikoError, "authentication_failed"):
            client.organizations()
        self.assertEqual(transport.post.call_count, 4)
        self.assertIsNone(client._token)

    def test_401_can_recover_once(self):
        client, transport = self.make_client(auth(), Response(401, {}), auth(5000), Response(200, {"organizations": []}))
        self.assertEqual(client.organizations()["organizations"], [])
        self.assertEqual(transport.post.call_count, 4)

    def test_credentials_rejected_without_retries(self):
        client, transport = self.make_client(Response(401, {"errorDescription": "private-api-key"}))
        with self.assertRaisesRegex(IikoError, "authentication_failed"):
            client.authenticate()
        self.assertEqual(transport.post.call_count, 1)

    def test_two_connections_same_external_ids_do_not_mix(self):
        left, lt = self.make_client(auth(), Response(200, {"guestCategories": [{"id": ORG, "name": "A"}]}))
        right, rt = self.make_client(auth(5000), Response(200, {"guestCategories": [{"id": ORG, "name": "B"}]}),
                                config=connection("other", "another-key"))
        a, b = left.categories(ORG), right.categories(ORG)
        self.assertNotEqual(a["connectionId"], b["connectionId"])
        self.assertNotEqual(a["guestCategories"], b["guestCategories"])
        self.assertNotEqual(lt.post.call_args.args[3], rt.post.call_args.args[3])
        self.assertEqual(rt.post.call_args_list[0].args[2]["apiKey"], "another-key")

    def test_same_slug_changed_credentials_do_not_share_token(self):
        a, at = self.make_client(auth())
        b, bt = self.make_client(auth(5000), config=connection(key="rotated-key"))
        a.authenticate()
        b.authenticate()
        self.assertEqual(bt.post.call_args.args[2]["apiKey"], "rotated-key")
        self.assertNotEqual(a._token, b._token)

    def test_connection_cannot_be_replaced_on_a_live_client(self):
        client, _ = self.make_client(auth())
        client.authenticate()
        with self.assertRaises(AttributeError):
            client.config = connection("other", "other-key")

    def test_secret_error_text_and_trace_are_not_exposed(self):
        secrets = ["private-app-id", "private-client-secret", "private-api-key", token(), "track-999"]
        client, _ = self.make_client(auth(), Response(403, {"errorDescription": " ".join(secrets),
                                                      "error": " ".join(secrets), "correlationId": "private-api-key"}))
        with mock.patch("logging.Logger._log") as log:
            try:
                client.organizations()
            except IikoError as exc:
                text = str(exc) + repr(exc) + traceback.format_exc() + repr(client.config)
            else:
                self.fail("Expected access denial")
        for secret in secrets:
            self.assertNotIn(secret, text)
        log.assert_not_called()

    def test_access_denied_keeps_valid_correlation_and_no_retry(self):
        client, transport = self.make_client(auth(), Response(403, {"correlationId": TRACE}))
        with self.assertRaises(IikoError) as raised:
            client.programs(ORG)
        self.assertEqual(raised.exception.code, "access_denied")
        self.assertEqual(raised.exception.correlation_id, TRACE)
        self.assertEqual(transport.post.call_count, 2)

    def test_read_post_network_retries_are_bounded(self):
        client, transport = self.make_client(auth(), *[IikoError("network_unavailable") for _ in range(3)])
        with self.assertRaisesRegex(IikoError, "network_unavailable"):
            client.categories(ORG)
        self.assertEqual(transport.post.call_count, 4)
        self.assertEqual(client._sleep.call_args_list, [mock.call(1), mock.call(2)])
        self.assertTrue(all(c.args[1] == PATHS["categories"] for c in transport.post.call_args_list[1:]))

    def test_rate_limit_retry_after_and_transient_recovery(self):
        client, transport = self.make_client(auth(), Response(429, {}, "3"), Response(503, {}),
                                        Response(200, {"guestCategories": []}))
        self.assertEqual(client.categories(ORG)["guestCategories"], [])
        self.assertEqual(client._sleep.call_args_list, [mock.call(3), mock.call(2)])
        self.assertEqual(transport.post.call_count, 4)

    def test_long_retry_after_does_not_retry_early(self):
        client, transport = self.make_client(Response(429, {}, "600"))
        with self.assertRaisesRegex(IikoError, "rate_limited"):
            client.authenticate()
        client._sleep.assert_not_called()
        self.assertEqual(transport.post.call_count, 1)

    def test_http_date_retry_after(self):
        client, _ = self.make_client()
        self.assertEqual(client._delay("Thu, 01 Jan 1970 00:16:45 GMT", 0), 5)

    def test_not_found_is_not_falsely_reported_as_confirmed_absence(self):
        for status in (400, 404):
            client, transport = self.make_client(auth(), Response(status, {"errorDescription": "card not found: 123456789"}))
            with self.subTest(status=status), self.assertRaises(IikoError) as raised:
                client.card(ORG, "123456789")
            self.assertEqual(raised.exception.status, status)
            self.assertNotIn("123456789", str(raised.exception))
            self.assertEqual(transport.post.call_count, 2)

    def test_missing_customer_is_not_success(self):
        client, _ = self.make_client(auth(), Response(200, {}))
        with self.assertRaisesRegex(IikoError, "customer_not_returned_unconfirmed"):
            client.card(ORG, "123456789")

    def test_card_projection_omits_profile_and_tracks(self):
        client, transport = self.make_client(auth(), Response(200, {
            "id": CUSTOMER, "name": "Private Name", "phone": "+79999999999", "userData": "private data",
            "cards": [{"id": TRACE, "number": "123456789", "track": "secret-track"}, {"number": "12"}],
            "categories": [{"id": ORG, "name": "Synthetic", "isActive": True}],
            "walletBalances": [{"id": TRACE, "name": "Synthetic", "type": 0, "balance": 125.5}]}))
        result = client.card(ORG, "123456789")
        text = json.dumps(result)
        for private in ("Private Name", "+79999999999", "private data", "secret-track", "123456789"):
            self.assertNotIn(private, text)
        self.assertEqual(result["card"], "****6789")
        self.assertEqual(result["cards"][1]["number"], "****")
        self.assertEqual(result["walletBalances"][0]["balance"], 125.5)
        self.assertEqual(transport.post.call_args.args[2], {"organizationId": ORG, "type": "cardNumber", "cardNumber": "123456789"})

    def test_categories_and_capitalized_programs_contract(self):
        client, transport = self.make_client(auth(), Response(200, {"guestCategories": [{"id": ORG, "isDefaultForNewGuests": False}]}),
                                        Response(200, {"Programs": [{"id": TRACE, "walletId": CUSTOMER, "appliedOrganizations": [ORG]}]}))
        self.assertFalse(client.categories(ORG)["guestCategories"][0]["isDefaultForNewGuests"])
        self.assertEqual(client.programs(ORG)["Programs"][0]["walletId"], CUSTOMER)
        self.assertTrue(transport.post.call_args.args[2]["withoutMarketingCampaigns"])

    def test_authorized_display_preserves_full_numbers_but_not_tracks(self):
        client, _ = self.make_client(auth(), Response(200, {
            "id": CUSTOMER, "name": "Private Name", "phone": "+79999999999",
            "cards": [{"id": TRACE, "number": "00123456789", "track": "secret-track"}, {"number": "12"}],
            "categories": [], "walletBalances": [],
        }))
        result = client.card(ORG, "00123456789", reveal_numbers=True)
        self.assertEqual(result["card"], "00123456789")
        self.assertEqual([card["number"] for card in result["cards"]], ["00123456789", "12"])
        for private in ("secret-track", "Private Name", "+79999999999"):
            self.assertNotIn(private, json.dumps(result))

    def test_malformed_lists_and_error_envelopes_fail_closed(self):
        for body in ({"programs": []}, {"Programs": ["bad"]}, {"Programs": None}, {"errorDescription": "secret"}):
            client, _ = self.make_client(auth(), Response(200, body))
            with self.subTest(body=body), self.assertRaises(IikoError):
                client.programs(ORG)

    def test_invalid_organization_has_no_network(self):
        client, transport = self.make_client()
        with self.assertRaisesRegex(IikoError, "invalid_organization_id"):
            client.categories("bad")
        transport.post.assert_not_called()

    def test_no_writes_in_allowlist(self):
        self.assertEqual(set(PATHS), {"auth", "organizations", "categories", "programs", "card"})


class TransportTests(SimpleTestCase):
    @mock.patch("iiko.client.http.client.HTTPSConnection")
    def test_tls_connect_and_read_timeouts_no_redirect(self, https):
        conn = https.return_value
        response = conn.getresponse.return_value
        response.status = 302
        response.read.return_value = b"{}"
        response.getheader.return_value = None
        result = Transport().post(connection(), PATHS["auth"], {"apiKey": "secret"})
        self.assertEqual(https.call_args.kwargs["timeout"], 5)
        ctx = https.call_args.kwargs["context"]
        self.assertTrue(ctx.check_hostname)
        self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)
        conn.sock.settimeout.assert_called_once_with(20)
        self.assertEqual(result.status, 302)
        self.assertEqual(conn.request.call_count, 1)
        conn.close.assert_called_once()

    @mock.patch("iiko.client.http.client.HTTPSConnection")
    def test_timeout_and_tls_errors_sanitized(self, https):
        for cause, code in ((TimeoutError("secret-key"), "network_unavailable"), (ssl.SSLError("secret-key"), "tls_error")):
            https.return_value.connect.side_effect = cause
            try:
                Transport().post(connection(), PATHS["auth"], {})
            except IikoError as exc:
                self.assertEqual(exc.code, code)
                self.assertNotIn("secret-key", traceback.format_exc())
            else:
                self.fail("Expected transport failure")


class ConfigurationAndCommandTests(SimpleTestCase):
    def test_file_is_literal_and_not_merged_into_process_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config"
            path.write_text("IIKO_API_KEY='literal$VALUE'\n", encoding="utf8")
            self.assertEqual(read_env_file(path), {"IIKO_API_KEY": "literal$VALUE"})
            path.write_text("UNKNOWN=secret", encoding="utf8")
            with self.assertRaises(ConfigurationError) as raised:
                read_env_file(path)
            self.assertNotIn("secret", str(raised.exception))

    def test_missing_fields_invalid_host_and_limits(self):
        with self.assertRaises(ConfigurationError):
            Connection.from_env({})
        for overrides in ({"base_url": "https://attacker.example"}, {"read_timeout": float("nan")},
                          {"connect_timeout": 0}, {"max_retries": 3}, {"connection_id": "../bad"}):
            args = {"connection_id": "test", "app_id": "app", "client_secret": "secret", "api_key": "key"}
            with self.subTest(overrides=overrides), self.assertRaises(ConfigurationError):
                Connection(**(args | overrides))

    @mock.patch("iiko.management.commands.iiko_probe.Connection.from_env", return_value=connection())
    @mock.patch("iiko.management.commands.iiko_probe.IikoClient")
    def test_config_command_does_not_call_network_or_print_values(self, client, config):
        output = io.StringIO()
        call_command("iiko_probe", "config", stdout=output)
        client.assert_not_called()
        self.assertIn("Values hidden", output.getvalue())
        self.assertNotIn("private", output.getvalue())

    @mock.patch("iiko.management.commands.iiko_probe.Connection.from_env", return_value=connection())
    @mock.patch("iiko.management.commands.iiko_probe.getpass.getpass", return_value="123456789")
    @mock.patch("iiko.management.commands.iiko_probe.IikoClient")
    def test_card_is_private_prompt_not_command_argument(self, client, prompt, config):
        output = io.StringIO()
        client.return_value.card.return_value = {"card": mask_card("123456789")}
        call_command("iiko_probe", "card", organization=ORG, stdout=output)
        prompt.assert_called_once()
        client.return_value.card.assert_called_once_with(ORG, "123456789")
        self.assertNotIn("123456789", output.getvalue())

    @mock.patch("iiko.management.commands.iiko_probe.Connection.from_env", return_value=connection())
    @mock.patch("iiko.management.commands.iiko_probe.IikoClient")
    def test_catalog_failure_does_not_hide_other_permissions(self, client, config):
        client.return_value.organizations.return_value = {"organizations": [{"id": ORG}]}
        client.return_value.categories.side_effect = IikoError("access_denied", status=403)
        client.return_value.programs.return_value = {"Programs": []}
        output = io.StringIO()
        with self.assertRaises(CommandError):
            call_command("iiko_probe", "catalogs", stdout=output)
        client.return_value.programs.assert_called_once_with(ORG)
        self.assertIn("access_denied", output.getvalue())
        self.assertIn('"count": 0', output.getvalue())

    def test_catalog_comparison_is_independent_of_item_order(self):
        categories = [{"id": ORG, "name": "A"}, {"id": TRACE, "name": "B"}]
        result = {"connectionId": "test", "organizations": [
            {"organizationId": org, "name": "Synthetic", "categories": {"guestCategories": cats},
             "programs": {"Programs": []}} for org, cats in ((ORG, categories), (TRACE, categories[::-1]))]}
        summary = catalog_summary(result)
        self.assertEqual(summary["distinctCategoryCatalogs"], 1)
        self.assertEqual(summary["organizations"][0]["categories"]["count"], 2)

    @mock.patch("iiko.management.commands.iiko_probe.Connection.from_env", return_value=connection())
    @mock.patch("iiko.management.commands.iiko_probe.IikoClient")
    def test_card_file_reads_selected_number_without_prompt_or_echo(self, client, config):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test-card.txt"
            path.write_text("00123456789\n", encoding="utf8")
            client.return_value.card.return_value = {"card": "****6789"}
            output = io.StringIO()
            call_command("iiko_probe", "card", organization=ORG, card_file=str(path), stdout=output)
            client.return_value.card.assert_called_once_with(ORG, "00123456789")
            self.assertNotIn("00123456789", output.getvalue())

    @mock.patch("iiko.management.commands.iiko_probe.Connection.from_env", return_value=connection())
    @mock.patch("iiko.management.commands.iiko_probe.IikoClient")
    def test_missing_card_file_does_not_call_iiko(self, client, config):
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(CommandError):
            call_command("iiko_probe", "card", organization=ORG, card_file=str(Path(directory) / "missing"))
        client.return_value.card.assert_not_called()
