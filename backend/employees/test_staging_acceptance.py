"""Acceptance regressions: assert the contract, never turn unexpected errors into wins."""
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import close_old_connections, connections, transaction
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import AccessToken

from accounts.authentication import ActiveEmployeeJWTAuthentication
from events.models import OutboxEvent
from .models import Employee, EmployeeInvitation
from .onboarding import InvitationService
from .onboarding_lifecycle import OnboardingService, OnboardingTemplateService
from .services import AccountAccessService


class PeopleStagingContractTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_user(
            username="acceptance-actor", email="acceptance-actor@example.test",
        )
        self.user = get_user_model().objects.create_user(
            username="acceptance-employee", email="acceptance-employee@example.test",
        )
        self.employee = Employee.objects.create(
            user=self.user, first_name="Synthetic", employee_number="ACCEPTANCE-1",
            work_email="acceptance-employee@example.test",
        )

    def test_access_suspend_restore_performs_real_state_changes(self):
        AccountAccessService.set_access(employee=self.employee, actor_user=self.actor,
                                       enabled=False, action="suspended")
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        AccountAccessService.set_access(employee=self.employee, actor_user=self.actor,
                                       enabled=True, action="restored")
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_access_audit_failure_rolls_back_state(self):
        with patch("employees.services.AuditService.record", side_effect=RuntimeError("audit unavailable")):
            with self.assertRaises(RuntimeError):
                AccountAccessService.set_access(employee=self.employee, actor_user=self.actor,
                                               enabled=False, action="suspended")
        self.user.refresh_from_db()
        self.employee.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertEqual(self.employee.account_access_state, "normal")

    def test_suspended_credentials_do_not_revive_after_restore(self):
        token = AccessToken.for_user(self.user)
        authentication = ActiveEmployeeJWTAuthentication()
        AccountAccessService.set_access(employee=self.employee, actor_user=self.actor,
                                       enabled=False, action="suspended")
        with self.assertRaises(AuthenticationFailed):
            authentication.get_user(token)
        AccountAccessService.set_access(employee=self.employee, actor_user=self.actor,
                                       enabled=True, action="restored")
        with self.assertRaises(AuthenticationFailed):
            authentication.get_user(token)

    def test_expiry_worker_is_idempotent(self):
        employee = Employee.objects.create(first_name="Invite", employee_number="ACCEPTANCE-2")
        invitation, _ = InvitationService.issue(
            employee=employee, actor_user=self.actor, delivery_address="invite@example.test",
        )
        EmployeeInvitation.objects.filter(pk=invitation.pk).update(
            created_at=timezone.now() - timedelta(days=3),
            expires_at=timezone.now() - timedelta(days=1),
        )
        call_command("process_onboarding", batch_size=1)
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, "expired")
        version = invitation.version
        count = OutboxEvent.objects.filter(event_type="people.invitation.expired").count()
        self.assertEqual(count, 1)
        call_command("process_onboarding", batch_size=1)
        invitation.refresh_from_db()
        self.assertEqual(invitation.version, version)
        self.assertEqual(OutboxEvent.objects.filter(event_type="people.invitation.expired").count(), count)

    def test_task_step_cannot_be_manually_completed_before_task(self):
        from .models import AssignmentTarget
        from work_tasks.models import TaskTemplate
        target = AssignmentTarget.objects.create(target_type="employee", employee=self.employee)
        work_template = TaskTemplate.objects.create(
            name="Acceptance", task_title="Acceptance", responsible_target=target,
            created_by=self.employee,
        )
        template = OnboardingTemplateService.create(actor_user=self.actor, name="Acceptance")
        OnboardingTemplateService.publish(template=template, actor_user=self.actor, expected_version=1,
            steps=[{"key": "work", "title": "Work", "step_type": "task",
                    "task_template": work_template, "responsible_strategy": "self"}])
        template.refresh_from_db()
        instance = OnboardingService.assign(employee=self.employee, actor_user=self.actor, template=template)
        step = instance.steps.get()
        with self.assertRaises(ValidationError):
            OnboardingService.step_action(step=step, actor_employee=self.employee,
                actor_user=self.user, expected_version=step.version, action="complete")


class PeopleStagingConcurrencyTests(TransactionTestCase):
    def parallel(self, operations):
        barrier = Barrier(len(operations), timeout=10)

        def run(operation):
            close_old_connections()
            try:
                with transaction.atomic():
                    with connections['default'].cursor() as cursor:
                        cursor.execute("SET LOCAL lock_timeout = '5s'")
                        cursor.execute("SET LOCAL statement_timeout = '10s'")
                    barrier.wait()
                    operation()
                return True
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(operations)) as pool:
            futures = [pool.submit(run, operation) for operation in operations]
            self.assertEqual([future.result(timeout=30) for future in futures], [True] * len(operations))

    def test_two_expiry_workers_publish_once(self):
        actor = get_user_model().objects.create_user(username="acceptance-worker", email="worker@example.test")
        employee = Employee.objects.create(first_name="Synthetic", employee_number="ACCEPTANCE-W")
        invitation, _ = InvitationService.issue(employee=employee, actor_user=actor,
                                               delivery_address="worker-invite@example.test")
        EmployeeInvitation.objects.filter(pk=invitation.pk).update(
            created_at=timezone.now() - timedelta(days=3), expires_at=timezone.now() - timedelta(days=1))
        self.parallel([lambda: call_command("process_onboarding", batch_size=1)] * 2)
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, "expired")
        self.assertEqual(invitation.version, 2)
        self.assertEqual(OutboxEvent.objects.filter(event_type="people.invitation.expired").count(), 1)

    def test_suspend_restore_race_both_operations_succeed(self):
        user = get_user_model().objects.create_user(username="acceptance-race", email="race@example.test")
        employee = Employee.objects.create(user=user, first_name="Synthetic", employee_number="ACCEPTANCE-R")
        self.parallel([
            lambda: AccountAccessService.set_access(employee=employee, actor_user=user, enabled=False, action="suspended"),
            lambda: AccountAccessService.set_access(employee=employee, actor_user=user, enabled=True, action="restored"),
        ])
        employee.refresh_from_db()
        user.refresh_from_db()
        self.assertEqual(user.is_active, employee.account_access_state == "normal")
        self.assertEqual(user.auth_version, 2)
        self.assertEqual(OutboxEvent.objects.filter(event_type__in=["people.account.suspended", "people.account.restored"]).count(), 2)
