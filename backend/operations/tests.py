from datetime import timedelta

from django.conf import settings
from django.test import TestCase, override_settings
from django.utils import timezone
from django.core.cache import cache
from rest_framework.test import APIClient

from accounts.models import User
from employees.models import Employee
from .models import WorkerHeartbeat


class ReleaseHardeningSecurityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="disabled", email="disabled@example.test", password="CorrectHorseBatteryStaple")
        self.employee = Employee.objects.create(user=self.user, employee_number="HARD-1", is_active=False)
        self.admin = User.objects.create_superuser(username="admin", email="admin-hardening@example.test", password="CorrectHorseBatteryStaple")

    def test_disabled_employee_cannot_login(self):
        response = APIClient().post("/api/v1/auth/login/", {"email": self.user.email, "password": "CorrectHorseBatteryStaple"}, format="json")
        self.assertEqual(response.status_code, 401); self.assertNotIn(self.user.email, str(response.data))

    def test_disabled_user_cannot_login(self):
        user=User.objects.create_user(username="inactive-user",email="inactive-user@example.test",password="CorrectHorseBatteryStaple",is_active=False)
        response=APIClient().post("/api/v1/auth/login/",{"email":user.email,"password":"CorrectHorseBatteryStaple"},format="json")
        self.assertEqual(response.status_code,401)

    def test_unknown_wrong_password_and_disabled_accounts_share_public_error(self):
        client=APIClient(); payloads=[{"email":"unknown@example.test","password":"wrong"},{"email":self.user.email,"password":"wrong"},{"email":self.user.email,"password":"CorrectHorseBatteryStaple"}]
        responses=[client.post("/api/v1/auth/login/",payload,format="json") for payload in payloads]
        self.assertEqual({response.status_code for response in responses},{401}); self.assertEqual(len({response.content for response in responses}),1)

    def test_disabled_employee_refresh_is_revoked(self):
        active=User.objects.create_user(username="active",email="active@example.test",password="CorrectHorseBatteryStaple")
        employee=Employee.objects.create(user=active,employee_number="HARD-2")
        login=APIClient().post("/api/v1/auth/login/",{"email":active.email,"password":"CorrectHorseBatteryStaple"},format="json")
        employee.is_active=False;employee.save(update_fields=("is_active",))
        response=APIClient().post("/api/v1/auth/refresh/",{"refresh":login.data["refresh"]},format="json")
        self.assertEqual(response.status_code,401)
        response=APIClient().get("/api/v1/auth/me/",HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        self.assertEqual(response.status_code,401)

    def test_refresh_rotation_and_logout_blacklist_old_tokens(self):
        user=User.objects.create_user(username="rotation",email="rotation@example.test",password="CorrectHorseBatteryStaple")
        Employee.objects.create(user=user,employee_number="HARD-3")
        client=APIClient();login=client.post("/api/v1/auth/login/",{"email":user.email,"password":"CorrectHorseBatteryStaple"},format="json");refresh_a=login.data["refresh"]
        rotated=client.post("/api/v1/auth/refresh/",{"refresh":refresh_a},format="json");self.assertEqual(rotated.status_code,200);self.assertIn("refresh",rotated.data)
        self.assertEqual(client.post("/api/v1/auth/refresh/",{"refresh":refresh_a},format="json").status_code,401)
        refresh_b=rotated.data["refresh"];self.assertEqual(client.post("/api/v1/auth/logout/",{"refresh":refresh_b},format="json").status_code,200)
        self.assertEqual(client.post("/api/v1/auth/refresh/",{"refresh":refresh_b},format="json").status_code,401)
        self.assertLess(client.post("/api/v1/auth/logout/",{"refresh":refresh_b},format="json").status_code,500)

    def test_login_is_throttled_without_user_enumeration(self):
        client = APIClient()
        for _ in range(5): self.assertEqual(client.post("/api/v1/auth/login/", {"email": "missing@example.test", "password": "wrong"}, format="json").status_code, 401)
        self.assertEqual(client.post("/api/v1/auth/login/", {"email": "missing@example.test", "password": "wrong"}, format="json").status_code, 429)

    def test_request_id_is_safe_and_returned(self):
        response = APIClient().get("/api/v1/health/live/", HTTP_X_REQUEST_ID="not-a-uuid")
        self.assertEqual(response.status_code, 200); self.assertEqual(len(response["X-Request-ID"]), 36)

    def test_system_status_is_admin_only_and_detects_stale_worker(self):
        WorkerHeartbeat.objects.create(worker_name="sla", instance_id="one", last_seen_at=timezone.now()-timedelta(hours=1))
        client=APIClient(); client.force_authenticate(self.user); self.assertEqual(client.get("/api/internal/v1/system/status/").status_code, 403)
        client.force_authenticate(self.admin); response=client.get("/api/internal/v1/system/status/")
        self.assertEqual(response.status_code, 200)
        statuses={item["name"]:item["status"] for item in response.data["workers"]}
        self.assertEqual(statuses["sla"], "WORKER_STALE")
        self.assertEqual(statuses["notifications"], "WORKER_UNKNOWN")
        self.assertNotIn("DATABASE_URL", str(response.data))

    def test_heartbeat_has_unique_run_id(self):
        from .heartbeat import record_worker_cycle
        record_worker_cycle("schedule", processed=1)
        first=WorkerHeartbeat.objects.get(worker_name="schedule").metadata_safe["run_id"]
        record_worker_cycle("schedule", processed=1)
        heartbeat=WorkerHeartbeat.objects.get(worker_name="schedule")
        self.assertNotEqual(first, heartbeat.metadata_safe["run_id"])
        self.assertEqual(heartbeat.items_processed, 2)

    def test_system_status_uses_latest_instance_per_worker(self):
        WorkerHeartbeat.objects.create(worker_name="sla", instance_id="old", last_seen_at=timezone.now()-timedelta(hours=1))
        WorkerHeartbeat.objects.create(worker_name="sla", instance_id="current", last_seen_at=timezone.now())
        client=APIClient(); client.force_authenticate(self.admin)
        workers=client.get("/api/internal/v1/system/status/").data["workers"]
        sla=[item for item in workers if item["name"] == "sla"]
        self.assertEqual(len(sla), 1)
        self.assertEqual(sla[0]["instance"], "current")
        self.assertEqual(sla[0]["status"], "WORKER_OK")
