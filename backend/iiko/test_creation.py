import threading
from uuid import uuid4
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, SimpleTestCase, override_settings
from rest_framework.test import APIClient
from audit.models import AuditEvent
from events.models import OutboxEvent
from .client import IikoClient, IikoError, Response, WRITE_PATHS
from .creation import REFERENCE_CATEGORIES, PILOT_ORGANIZATION, TOPUP_WALLET
from .models import CardCreation, CardCategory
from .tests import connection, auth, CUSTOMER

URL = "/api/v1/iiko/connections/sheregesh/card/create/"


@override_settings(IIKO_CONNECTIONS={"sheregesh": {"organization_id": PILOT_ORGANIZATION}})
class CreationApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(username="creator", is_superuser=True)
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.client = mock.Mock()
        self.client.programs.return_value = {"Programs": [{"walletId": TOPUP_WALLET, "isActive": True}]}
        self.client.create_customer.return_value = CUSTOMER
        self.balance = 0
        def topup(org, customer, wallet, amount, operation): self.balance += float(amount)
        self.client.topup_wallet.side_effect = topup
        self.client.categories.return_value = {"guestCategories": [
            {"id": value, "isActive": True, "isDefaultForNewGuests": False} for value in REFERENCE_CATEGORIES.values()
        ]}
        def lookup(*args, **kwargs):
            if not kwargs.get("reveal_numbers"):
                raise IikoError("card_not_found")
            operation = CardCreation.objects.get(pk=self.data["operationId"])
            return {"customerId": str(operation.customer_id), "cards": [{"number": "00001234"}],
                    "categories": self.client.categories.return_value["guestCategories"], "walletBalances": [{"id": TOPUP_WALLET, "balance": self.balance}]}
        self.client.card.side_effect = lookup
        self.client.customer_by_track.side_effect = IikoError("card_not_found")
        mock.patch("iiko.create_views.Connection.from_env", return_value=connection()).start()
        mock.patch("iiko.views.client_for", return_value=(self.client, threading.BoundedSemaphore(1))).start()
        self.addCleanup(mock.patch.stopall)
        self.data = {"operationId": str(uuid4()), "cardNumber": "00001234", "surname": "Synthetic",
                     "name": "Test", "patronymic": "", "topupAmount": "10000.00", **REFERENCE_CATEGORIES}

    def post(self, **changes):
        return self.api.post(URL, {**self.data, **changes}, format="json")

    def test_success_uses_fresh_customer_and_verifies_categories_then_card(self):
        response = self.post()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "succeeded")
        operation = CardCreation.objects.get()
        self.client.create_customer.assert_called_once_with(PILOT_ORGANIZATION, number="00001234",
            name="Test", surname="Synthetic", patronymic="", comment="")
        self.assertEqual(str(operation.customer_id), CUSTOMER)
        self.assertEqual(self.client.add_category.call_count, 4)
        self.client.add_card.assert_not_called()
        self.assertEqual([call[0] for call in self.client.method_calls],
            ["programs", "categories", "card", "customer_by_track", "create_customer", "add_category", "add_category", "add_category", "add_category", "card", "topup_wallet", "card"])
        self.assertEqual(AuditEvent.objects.filter(action__startswith="iiko.card.creation.").count(), 2)
        self.assertEqual(OutboxEvent.objects.filter(event_type__startswith="iiko.card.creation.").count(), 2)
        persisted = str(list(CardCreation.objects.values())) + str(list(OutboxEvent.objects.values("payload"))) + str(list(AuditEvent.objects.values("new_values")))
        self.assertNotIn("00001234", persisted)
        self.assertNotIn("Synthetic", persisted)
        self.assertIn("no-store", response["Cache-Control"])

    def test_same_key_replays_receipt_without_any_remote_calls(self):
        self.post()
        self.client.reset_mock()
        self.assertEqual(self.post().data["status"], "succeeded")
        self.assertEqual(self.client.method_calls, [])
        self.assertEqual(CardCreation.objects.count(), 1)

    def test_topup_is_exactly_once_and_result_is_persisted(self):
        result = self.post(topupAmount="123.45")
        self.assertEqual(result.status_code, 201)
        op = CardCreation.objects.get()
        self.assertEqual(str(op.topup_amount), "123.45")
        self.assertEqual(str(op.topup_wallet_id), TOPUP_WALLET)
        self.assertTrue(op.topup_confirmed)
        self.assertEqual(op.topup_balance_before, 0)
        self.assertEqual(result.data["topupAmount"], "123.45")
        self.client.topup_wallet.assert_called_once()
        self.client.reset_mock()
        self.assertEqual(self.post(topupAmount="123.45").data, result.data)
        self.assertEqual(self.client.method_calls, [])

    def test_uncertain_topup_is_not_repeated(self):
        def uncertain(*args):
            self.balance += 10000
            raise IikoError("network_unavailable")
        self.client.topup_wallet.side_effect = uncertain
        result = self.post()
        self.assertEqual(result.data["stage"], "topup_wallet")
        self.assertEqual(result.data["status"], "needs_review")
        self.assertFalse(result.data["topupConfirmed"])
        self.assertEqual(result.data["customerId"], CUSTOMER)
        self.post()
        self.assertEqual(self.post(operationId=str(uuid4())).status_code, 409)
        self.client.topup_wallet.assert_called_once()

    def test_topup_balance_mismatch_remains_uncertain(self):
        self.client.topup_wallet.side_effect = None
        result = self.post()
        self.assertEqual(result.data["stage"], "verify_topup")
        self.assertEqual(result.data["errorCode"], "topup_not_confirmed")
        self.assertEqual(result.data["status"], "needs_review")

    def test_invalid_amount_and_unavailable_wallet_prevent_creation(self):
        for amount in ("", "-1", "0", "NaN", "1.001", "10000000000"):
            self.assertEqual(self.post(topupAmount=amount).status_code, 400)
        self.assertEqual(self.client.method_calls, [])
        self.client.programs.return_value = {"Programs": []}
        self.assertEqual(self.post().data["errorCode"], "topup_wallet_unavailable")
        self.client.create_customer.assert_not_called()
        self.client.topup_wallet.assert_not_called()

    def test_food_card_cap_applies_to_prepare_and_create_before_any_io(self):
        for suffix in ("prepare/", "create/"):
            response = self.api.post(URL.replace("create/", suffix), {**self.data, "topupAmount": "10000.01"}, format="json")
            self.assertEqual(response.status_code, 400)
            self.assertIn("10 000", str(response.data))
        self.assertEqual(self.client.method_calls, [])
        self.assertFalse(CardCreation.objects.exists())

    def test_food_cap_boundary_and_other_card_types(self):
        from .create_views import CreateInput
        for amount in ("9999.99", "10000.00"):
            serializer = CreateInput(data={**self.data, "topupAmount": amount})
            self.assertTrue(serializer.is_valid(), serializer.errors)
        for name in ("Депозитная карта", "Карта партнера"):
            category = CardCategory.objects.get(field="cardType", name=name)
            serializer = CreateInput(data={**self.data, "cardType": str(category.external_id), "topupAmount": "10000.01"})
            self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_revoked_topup_permission_prevents_all_external_calls(self):
        with mock.patch("iiko.create_views.CanTopupIikoCard.has_permission", return_value=False):
            self.assertEqual(self.post().status_code, 403)
        self.assertEqual(self.client.method_calls, [])

    def test_diagnostics_survive_status_read_without_copying_to_audit(self):
        detail = {"endpoint": "/test", "fields": {"errorDescription": "Synthetic diagnostic detail"}}
        self.client.create_customer.side_effect = IikoError("write_not_confirmed", status=400, diagnostics=detail)
        response = self.post()
        self.assertEqual(response.data["diagnostics"], detail)
        operation = CardCreation.objects.get()
        self.assertEqual(operation.error_diagnostics, detail)
        self.client.reset_mock()
        status = self.api.get(URL.replace("create/", "operations/" + str(operation.pk) + "/"))
        self.assertEqual(status.data["diagnostics"], detail)
        self.assertEqual(self.client.method_calls, [])
        persisted = str(list(OutboxEvent.objects.values())) + str(list(AuditEvent.objects.values()))
        self.assertNotIn("Synthetic diagnostic detail", persisted)

    def test_multiline_comment_is_forwarded_without_plaintext_persistence(self):
        comment = "  Дополнительные сведения\nВторая строка\tтекст  "
        self.assertEqual(self.post(comment=comment).status_code, 201)
        self.assertEqual(self.client.create_customer.call_args.kwargs["comment"], comment)
        persisted = str(list(CardCreation.objects.values())) + str(list(OutboxEvent.objects.values())) + str(list(AuditEvent.objects.values()))
        self.assertNotIn("Дополнительные сведения", persisted)
        self.client.reset_mock()
        self.assertEqual(self.post(comment="Изменено").status_code, 409)
        self.assertEqual(self.client.method_calls, [])

    def test_invalid_comment_is_rejected_before_remote_calls(self):
        for value in ["x" * 2001, "bad\x00text", 123]:
            self.assertEqual(self.post(comment=value).status_code, 400)
        self.assertEqual(self.client.method_calls, [])

    def test_changed_payload_key_or_new_key_same_card_rejected(self):
        self.post()
        self.client.reset_mock()
        self.assertEqual(self.post(name="Changed").status_code, 409)
        self.assertEqual(self.post(operationId=str(uuid4())).status_code, 409)
        self.assertEqual(self.client.method_calls, [])

    def test_preflight_errors_never_write(self):
        for code in ("card_occupied", "bad_request", "not_found_unconfirmed", "network_unavailable"):
            with self.subTest(code=code):
                self.data["operationId"] = str(uuid4())
                self.client.card.side_effect = None if code == "card_occupied" else IikoError(code)
                response = self.post()
                self.assertEqual(response.data["status"], "failed")
                self.assertEqual(response.data["stage"], "preflight")
        self.client.create_customer.assert_not_called()
        self.client.add_card.assert_not_called()

    def test_occupied_track_never_writes(self):
        self.client.customer_by_track.side_effect = None
        self.assertEqual(self.post().data["errorCode"], "card_occupied")
        self.client.create_customer.assert_not_called()

    def test_invalid_or_extra_default_categories_never_write(self):
        self.client.categories.return_value["guestCategories"][0]["isActive"] = False
        self.assertEqual(self.post().data["errorCode"], "reference_unavailable")
        self.data["operationId"] = str(uuid4())
        self.client.categories.return_value["guestCategories"][0]["isActive"] = True
        self.client.categories.return_value["guestCategories"].append({"id": str(uuid4()), "isActive": True, "isDefaultForNewGuests": True})
        self.assertEqual(self.post().data["errorCode"], "unexpected_default_categories")
        self.client.create_customer.assert_not_called()

    def test_partial_category_failure_blocks_card_and_replays(self):
        self.client.add_category.side_effect = [None, IikoError("network_unavailable")]
        result = self.post().data
        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(result["stage"], "category_department")
        self.assertEqual(len(result["completedCategories"]), 1)
        self.client.add_card.assert_not_called()
        self.client.reset_mock()
        self.assertEqual(self.post().data, result)
        self.assertEqual(self.post(operationId=str(uuid4())).status_code, 409)
        self.assertEqual(self.client.method_calls, [])

    def test_unknown_customer_creation_and_verification_failure_do_not_replay(self):
        self.client.create_customer.side_effect = IikoError("network_unavailable")
        self.assertEqual(self.post().data["status"], "needs_review")
        self.client.create_customer.assert_called_once()
        self.client.add_category.assert_not_called()
        self.post()
        self.client.create_customer.assert_called_once()

    def test_rejected_write_preserves_http_status_and_trace(self):
        self.client.create_customer.side_effect = IikoError("write_not_confirmed", status=403, correlation_id=CUSTOMER)
        result = self.post().data
        self.assertEqual(result["httpStatus"], 403)
        self.assertEqual(result["correlationId"], CUSTOMER)
        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(self.post().data, result)
        self.client.create_customer.assert_called_once()

    def test_wrong_verified_owner_is_not_success(self):
        original = self.client.card.side_effect
        def lookup(*args, **kwargs):
            result = original(*args, **kwargs)
            result["customerId"] = str(uuid4())
            return result
        self.client.card.side_effect = lookup
        result = self.post().data
        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(result["errorCode"], "verification_mismatch")

    def test_running_record_after_crash_is_not_replayed(self):
        with mock.patch("iiko.creation.record", side_effect=[None, RuntimeError("private")]):
            self.assertEqual(self.post().status_code, 503)
        self.client.reset_mock()
        self.assertEqual(self.post().data["status"], "running")
        self.assertEqual(self.client.method_calls, [])

    def test_outbox_failure_before_start_prevents_writes(self):
        with mock.patch("iiko.creation.DomainEventService.publish", side_effect=RuntimeError("private")):
            response = self.post()
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private", str(response.data))
        self.assertEqual(CardCreation.objects.count(), 0)
        self.assertEqual(self.client.method_calls, [])

    def test_input_cannot_override_scope_guest_wallet_or_category(self):
        for change in ({"organizationId": CUSTOMER}, {"customerId": CUSTOMER}, {"balance": "10000"},
                       {"legalEntity": CUSTOMER}, {"cardNumber": 123}, {"surname": "  "}, {"name": "a\nb"}):
            with self.subTest(change=change):
                self.assertEqual(self.post(**change).status_code, 400)
        self.assertEqual(self.client.method_calls, [])

    def test_create_permission_and_status_isolation(self):
        self.post()
        self.user.is_superuser = False
        self.user.save()
        with mock.patch("iiko.views.PermissionService.has_permission", return_value=False) as permission:
            self.assertEqual(self.post().status_code, 403)
            self.assertEqual(permission.call_args.kwargs["permission"], "iiko.sheregesh.card.create")
        other = get_user_model().objects.create_user(username="other", email="other@example.invalid")
        self.api.force_authenticate(other)
        status_url = URL.replace("create/", "operations/" + self.data["operationId"] + "/")
        with mock.patch("iiko.views.PermissionService.has_permission", return_value=True):
            self.assertEqual(self.api.get(status_url).status_code, 404)
        self.api.force_authenticate(self.user)
        with mock.patch("iiko.views.PermissionService.has_permission", return_value=True):
            self.assertEqual(self.api.get(status_url).data["status"], "succeeded")
        self.api.force_authenticate(None)
        self.assertEqual(self.post().status_code, 401)

    def test_catalog_contains_user_lists_and_reference_department(self):
        response = self.api.get(URL.replace("create/", "catalog/"))
        self.assertEqual(response.status_code, 200)
        fields = response.data["fields"]
        self.assertEqual([row["name"] for row in fields["department"]], [
            "Грелка", "О!Пушка", "Ресторан Елена", "Катадзе", "Wow Kitchen", "Wow Aparts",
            "AYS Hotel", "Bunker", "Напойка", "Каритшал", "Профилак", "Стройка", "IT"])
        self.assertEqual(len(fields["legalEntity"]), 6)
        self.assertEqual([row["name"] for row in fields["cardType"]], ["Карта питания", "Депозитная карта", "Карта партнера"])
        self.assertEqual(self.client.method_calls, [])
        self.assertIn("no-store", response["Cache-Control"])

    def test_selected_categories_are_written_and_verified_instead_of_reference(self):
        for field, name in [("department", "Стройка"), ("legalEntity", "ООО Барс"), ("cardType", "Депозитная карта")]:
            self.data[field] = str(CardCategory.objects.get(field=field, name=name).external_id)
        selected = [self.data[field] for field in REFERENCE_CATEGORIES]
        self.client.categories.return_value = {"guestCategories": [{"id": value, "isActive": True} for value in selected]}
        self.assertEqual(self.post().data["status"], "succeeded")
        self.assertEqual([call.args[2] for call in self.client.add_category.call_args_list], selected)

    def test_category_from_different_field_or_connection_is_rejected(self):
        department = CardCategory.objects.get(name="Стройка")
        self.assertEqual(self.post(legalEntity=str(department.external_id)).status_code, 400)
        department.connection_id = "other"
        department.save()
        self.assertEqual(self.post(department=str(department.external_id)).status_code, 400)
        self.assertEqual(self.client.method_calls, [])
        response = self.api.get(URL.replace("create/", "catalog/"))
        self.assertNotIn("Стройка", [row["name"] for row in response.data["fields"]["department"]])

    def test_inactive_selected_category_stops_before_any_write(self):
        self.data["department"] = str(CardCategory.objects.get(name="Стройка").external_id)
        self.assertEqual(self.post().data["errorCode"], "reference_unavailable")
        self.client.create_customer.assert_not_called()


class MutationTransportTests(SimpleTestCase):
    def make_client(self, response):
        transport = mock.Mock()
        transport.post.side_effect = [auth(), response]
        return IikoClient(connection(), transport=transport, clock=lambda: 1000, sleep=mock.Mock()), transport

    def test_writes_never_retry(self):
        for response in (IikoError("network_unavailable"), Response(401, {}), Response(429, {}), Response(500, {})):
            with self.subTest(response=response):
                client, transport = self.make_client(response)
                with self.assertRaises(IikoError):
                    client.add_card(PILOT_ORGANIZATION, CUSTOMER, "00001234")
                self.assertEqual(transport.post.call_count, 2)
                client._sleep.assert_not_called()

    def test_create_uses_free_card_track_and_returns_server_id(self):
        client, transport = self.make_client(Response(200, {"id": CUSTOMER}))
        client.create_customer(PILOT_ORGANIZATION, number="00001234", name="Test", surname="Synthetic", patronymic="", comment="Текст\nСтрока")
        payload = transport.post.call_args.args[2]
        self.assertEqual(payload["comment"], "Текст\nСтрока")
        self.assertEqual(payload["surName"], "Synthetic")
        self.assertNotIn("id", payload)
        self.assertEqual(payload["cardTrack"], "00001234")
        self.assertEqual(payload["cardNumber"], "00001234")
        self.assertNotIn("phone", payload)
        self.assertFalse(payload["shouldReceivePromoActionsInfo"])
        self.assertEqual(transport.post.call_args.args[1], WRITE_PATHS["create_customer"])

    def test_missing_create_id_is_uncertain(self):
        client, _ = self.make_client(Response(200, {}))
        with self.assertRaisesRegex(IikoError, "write_not_confirmed"):
            client.create_customer(PILOT_ORGANIZATION, number="00001234", name="Test", surname="Synthetic", patronymic="")

    def test_only_observed_missing_number_envelope_means_absence(self):
        client, _ = self.make_client(Response(400, {"code": "Transport_WrongCardNumber", "errorCode": "Card_CanNotFindByNumber", "message": "private"}))
        with self.assertRaisesRegex(IikoError, "card_not_found"):
            client.card(PILOT_ORGANIZATION, "00001234")
        client, _ = self.make_client(Response(400, {"code": "Transport_WrongCardNumber"}))
        with self.assertRaisesRegex(IikoError, "bad_request"):
            client.card(PILOT_ORGANIZATION, "00001234")
