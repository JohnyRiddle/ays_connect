from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from audit.models import AuditEvent
from events.models import OutboxEvent
from .models import Employee, EmployeeInvitation, RegistrationRequest
from .onboarding import InvitationService, RegistrationService, token_hash


@override_settings(SECURE_SSL_REDIRECT=False)
class OnboardingTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(username="people-admin", email="people-admin@example.test", password="StrongAdmin123!")
        self.employee = Employee.objects.create(first_name="Анна", last_name="Тестова", employee_number="ONB-1")

    def issue(self): return InvitationService.issue(employee=self.employee, actor_user=self.admin, delivery_address="anna@example.test")

    def test_invitation_is_hash_only_expiring_and_audited(self):
        invitation, raw = self.issue()
        self.assertNotEqual(invitation.token_hash, raw); self.assertEqual(invitation.token_hash, token_hash(raw))
        self.assertGreater(invitation.expires_at, timezone.now())
        self.assertTrue(AuditEvent.objects.filter(action="employee.invitation.created").exists())
        self.assertTrue(OutboxEvent.objects.filter(event_type="employee.invitation.created").exists())

    def test_reissue_revokes_old_and_only_one_is_open(self):
        first, first_raw = self.issue(); second, _ = self.issue(); first.refresh_from_db()
        self.assertIsNotNone(first.revoked_at); self.assertIsNone(second.revoked_at); self.assertIsNone(InvitationService.context(first_raw))
        self.assertEqual(EmployeeInvitation.objects.filter(employee=self.employee, used_at__isnull=True, revoked_at__isnull=True).count(), 1)

    def test_revoke_expired_used_invalid_and_inactive_denied(self):
        invitation, raw = self.issue(); InvitationService.revoke(invitation=invitation, actor_user=self.admin)
        self.assertIsNone(InvitationService.context(raw))
        invitation, raw = self.issue(); invitation.expires_at = timezone.now() - timedelta(seconds=1); invitation.save(update_fields=["expires_at"])
        self.assertIsNone(InvitationService.context(raw))
        self.employee.is_active = False; self.employee.save(update_fields=["is_active"])
        with self.assertRaises(ValidationError): self.issue()

    def test_activation_links_user_once_without_roles(self):
        invitation, raw = self.issue()
        user = InvitationService.activate(token=raw, password="VeryStrongPass123!", password_confirmation="VeryStrongPass123!")
        self.employee.refresh_from_db(); invitation.refresh_from_db()
        self.assertEqual(self.employee.user, user); self.assertIsNotNone(invitation.used_at)
        self.assertEqual(self.employee.access_roles.count(), 0)
        with self.assertRaises(ValidationError): InvitationService.activate(token=raw, password="VeryStrongPass123!", password_confirmation="VeryStrongPass123!")

    def test_activation_validation_rolls_back(self):
        invitation, raw = self.issue(); before_audit = AuditEvent.objects.count(); before_outbox = OutboxEvent.objects.count()
        with self.assertRaises(ValidationError): InvitationService.activate(token=raw, password="short", password_confirmation="short")
        invitation.refresh_from_db(); self.employee.refresh_from_db()
        self.assertIsNone(invitation.used_at); self.assertIsNone(self.employee.user_id)
        self.assertEqual(AuditEvent.objects.count(), before_audit); self.assertEqual(OutboxEvent.objects.count(), before_outbox)

    def test_registration_is_generic_deduplicated_and_never_creates_employee(self):
        client = APIClient(); before = Employee.objects.count()
        one = client.post("/api/public/v1/register/", {"full_name": "Неизвестный", "email": "unknown@example.test"}, format="json")
        two = client.post("/api/public/v1/register/", {"full_name": "Другое имя", "email": "UNKNOWN@example.test"}, format="json")
        self.assertEqual(one.status_code, 202); self.assertEqual(one.json(), two.json())
        self.assertEqual(RegistrationRequest.objects.count(), 1); self.assertEqual(Employee.objects.count(), before)

    def test_registration_approve_and_reject(self):
        registration, _ = RegistrationService.create(full_name="Анна Тестова", email="anna@example.test")
        invitation, raw = RegistrationService.approve(registration=registration, employee=self.employee, actor_user=self.admin)
        registration.refresh_from_db(); self.assertEqual(registration.status, "approved"); self.assertIsNotNone(InvitationService.context(raw))
        other, _ = RegistrationService.create(full_name="Отказ", email="reject@example.test")
        RegistrationService.reject(registration=other, actor_user=self.admin, reason="not_found"); other.refresh_from_db()
        self.assertEqual(other.status, "rejected"); self.assertEqual(other.rejection_code, "not_found")

    def test_directory_idor_and_account_block(self):
        client = APIClient(); client.force_authenticate(self.admin)
        response = client.get("/api/internal/v1/people/employees/"); self.assertEqual(response.status_code, 200)
        invitation, raw = self.issue(); InvitationService.activate(token=raw, password="VeryStrongPass123!", password_confirmation="VeryStrongPass123!"); self.employee.refresh_from_db()
        response = client.post(f"/api/internal/v1/people/employees/{self.employee.pk}/account/block/"); self.assertEqual(response.status_code, 200)
        self.employee.user.refresh_from_db(); self.assertFalse(self.employee.user.is_active)
        response = client.post(f"/api/internal/v1/people/employees/{self.employee.pk}/account/unblock/"); self.assertEqual(response.status_code, 200)
        normal = get_user_model().objects.create_user(username="normal", email="normal@example.test", password="NormalPass123!")
        Employee.objects.create(user=normal, first_name="Обычный", employee_number="ONB-2")
        client.force_authenticate(normal); self.assertEqual(client.get(f"/api/internal/v1/people/employees/{self.employee.pk}/").status_code, 404)


class OnboardingConcurrencyTests(TransactionTestCase):
    reset_sequences = True
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(username="parallel-admin", email="parallel-admin@example.test", password="StrongAdmin123!")
        self.employee = Employee.objects.create(first_name="Параллель", employee_number="PAR-1")
        self.invitation, self.raw = InvitationService.issue(employee=self.employee, actor_user=self.admin, delivery_address="parallel@example.test")

    def activate(self):
        close_old_connections()
        try:
            InvitationService.activate(token=self.raw, password="ParallelPass123!", password_confirmation="ParallelPass123!"); return True
        except (ValidationError, Exception): return False
        finally: connections.close_all()

    def test_same_token_exactly_one_success(self):
        with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(lambda _: self.activate(), range(2)))
        self.assertEqual(results.count(True), 1)
        self.assertEqual(get_user_model().objects.filter(email="parallel@example.test").count(), 1)
        self.invitation.refresh_from_db(); self.assertIsNotNone(self.invitation.used_at)

    def issue_parallel(self):
        close_old_connections()
        try:
            InvitationService.issue(employee=self.employee, actor_user=self.admin, delivery_address="parallel@example.test"); return True
        except Exception: return False
        finally: connections.close_all()

    def test_concurrent_reissue_leaves_one_open_invitation(self):
        with ThreadPoolExecutor(max_workers=2) as pool: list(pool.map(lambda _: self.issue_parallel(), range(2)))
        self.assertEqual(EmployeeInvitation.objects.filter(employee=self.employee, used_at__isnull=True, revoked_at__isnull=True).count(), 1)
