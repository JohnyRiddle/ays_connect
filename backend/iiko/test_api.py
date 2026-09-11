import threading
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from access_control.models import EmployeeRole, Permission, Role, RolePermission, Scope
from employees.models import Employee
from .client import IikoError
from .tests import connection, ORG, CUSTOMER, TRACE
from .views import client_for


URL = "/api/v1/iiko/connections/sheregesh/card/check/"
RESULT = {"connectionId": "sheregesh", "organizationId": ORG, "card": "00123456789",
          "customerId": CUSTOMER, "cards": [], "categories": [], "walletBalances": []}


@override_settings(IIKO_CONNECTIONS={"sheregesh": {"organization_id": ORG}})
class CardApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(username="operator", email="operator@example.invalid")
        self.employee = Employee.objects.create(user=self.user, first_name="Synthetic")
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.client = mock.Mock()
        self.client.card.return_value = RESULT
        self.gate = threading.BoundedSemaphore(1)
        self.factory = mock.patch("iiko.views.client_for", return_value=(self.client, self.gate)).start()
        mock.patch("iiko.views.Connection.from_env", return_value=connection()).start()
        self.addCleanup(mock.patch.stopall)

    def grant(self, code="iiko.sheregesh.card.view", scope=Scope.GLOBAL):
        permission = Permission.objects.create(code=code, name="Read synthetic cards")
        role = Role.objects.create(code=code, name="Synthetic operator")
        RolePermission.objects.create(role=role, permission=permission, scope=scope)
        EmployeeRole.objects.create(employee=self.employee, role=role)

    def test_authentication_required(self):
        self.api.force_authenticate(None)
        response = self.api.post(URL, {"cardNumber": "00123456789"}, format="json")
        self.assertEqual(response.status_code, 401)
        self.assertIn("no-store", response["Cache-Control"])
        self.client.card.assert_not_called()

    def test_missing_permission_or_other_cabinet_does_not_read(self):
        self.grant("iiko.other.card.view")
        response = self.api.post(URL, {"cardNumber": "00123456789"}, format="json")
        self.assertEqual(response.status_code, 403)
        self.client.card.assert_not_called()

    def test_narrow_scope_is_not_global_cabinet_access(self):
        self.grant(scope=Scope.OWN)
        self.assertEqual(self.api.post(URL, {"cardNumber": "test"}, format="json").status_code, 403)
        self.client.card.assert_not_called()

    def test_inactive_employee_denied(self):
        self.grant()
        self.employee.is_active = False
        self.employee.save()
        self.assertEqual(self.api.post(URL, {"cardNumber": "test"}, format="json").status_code, 403)

    def test_global_grant_reads_server_selected_organization(self):
        self.grant()
        response = self.api.post(URL, {"cardNumber": "00123456789"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, RESULT)
        self.assertIn("no-store", response["Cache-Control"])
        self.client.card.assert_called_once_with(ORG, "00123456789", reveal_numbers=True, include_owner=True)
        self.assertEqual(response.data["card"], "00123456789")

    def test_superuser_can_check_but_cannot_change(self):
        self.user.is_superuser = True
        self.user.save()
        self.assertEqual(self.api.post(URL, {"cardNumber": "test"}, format="json").status_code, 200)
        self.assertEqual(self.api.delete(URL).status_code, 405)

    def test_user_cannot_supply_scope_track_or_batch(self):
        self.grant()
        for data in ({"cardNumber": "test", "organizationId": TRACE}, {"cardNumber": "test", "cardTrack": "secret"},
                     {"cardNumber": ["1", "2"]}, {"cardNumber": 123}, {"cardNumber": ""},
                     {"cardNumber": "a\nb"}, {"cardNumber": "a" * 257}):
            with self.subTest(data=data):
                self.assertEqual(self.api.post(URL, data, format="json").status_code, 400)
        self.client.card.assert_not_called()

    def test_unknown_connection_denied(self):
        self.grant()
        self.assertEqual(self.api.post(URL.replace("sheregesh", "other"), {"cardNumber": "test"}, format="json").status_code, 404)
        self.client.card.assert_not_called()

    def test_configuration_cannot_mix_connections(self):
        self.grant()
        with mock.patch("iiko.views.Connection.from_env", return_value=connection("other")):
            self.assertEqual(self.api.post(URL, {"cardNumber": "test"}, format="json").status_code, 503)
        self.client.card.assert_not_called()

    def test_upstream_errors_are_safe_and_gate_released(self):
        self.grant()
        self.client.card.side_effect = IikoError("bad_request", status=400, correlation_id=TRACE)
        response = self.api.post(URL, {"cardNumber": "00123456789"}, format="json")
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["error"]["correlationId"], TRACE)
        self.assertNotIn("00123456789", response.content.decode())
        self.assertTrue(self.gate.acquire(blocking=False))

    def test_unexpected_error_cannot_expose_debug_traceback(self):
        self.grant()
        self.client.card.side_effect = ValueError("secret-token 00123456789")
        response = self.api.post(URL, {"cardNumber": "00123456789"}, format="json")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("secret-token", response.content.decode())
        self.assertNotIn("00123456789", response.content.decode())

    def test_busy_connection_does_not_queue(self):
        self.grant()
        self.gate.acquire()
        self.assertEqual(self.api.post(URL, {"cardNumber": "test"}, format="json").status_code, 429)
        self.client.card.assert_not_called()

    def test_throttle_prevents_repeated_lookup(self):
        self.grant()
        for _ in range(10):
            self.assertEqual(self.api.post(URL, {"cardNumber": "test"}, format="json").status_code, 200)
        self.assertEqual(self.api.post(URL, {"cardNumber": "test"}, format="json").status_code, 429)
        self.assertEqual(self.client.card.call_count, 10)

    def test_client_cache_isolates_connection_and_rotated_credentials(self):
        # Use the real cached factory; no network calls.
        client_for.cache_clear()
        a = client_for(connection())[0]
        self.assertIs(a, client_for(connection())[0])
        self.assertIsNot(a, client_for(connection("other"))[0])
        self.assertIsNot(a, client_for(connection(key="rotated"))[0])
        client_for.cache_clear()
