from concurrent.futures import ThreadPoolExecutor

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connections
from django.test import TestCase, TransactionTestCase

from audit.models import AuditEvent
from events.models import OutboxEvent
from .models import AssignmentTarget, Employee, EmployeeInvitation, FirstLoginProgress, OnboardingInstance, OnboardingTemplate
from .onboarding import FirstLoginService, InvitationService, account_status
from .onboarding_lifecycle import OnboardingConflict, OnboardingService, OnboardingTemplateService
from .services import EmployeeService


class Phase24Tests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(username="phase24-admin", email="phase24-admin@example.test", password="StrongAdmin123!")
        self.employee = Employee.objects.create(first_name="Новый", last_name="Сотрудник", employee_number="P24-1", work_email="new@example.test")

    def template(self, steps=None):
        template = OnboardingTemplateService.create(actor_user=self.admin, name="Базовый", scope="global")
        OnboardingTemplateService.publish(template=template, actor_user=self.admin, expected_version=1, steps=steps or [
            {"key":"profile", "title":"Заполнить профиль", "step_type":"profile", "required":True, "responsible_strategy":"self"},
        ])
        template.refresh_from_db(); return template

    def test_invitation_lifecycle_and_first_login(self):
        invitation, raw = InvitationService.issue(employee=self.employee, actor_user=self.admin, delivery_address=self.employee.work_email)
        self.assertEqual(invitation.status, "created"); self.assertNotIn(raw, invitation.token_hash); self.assertEqual(account_status(self.employee), "INVITED")
        user = InvitationService.activate(token=raw, password="Phase24Strong123!", password_confirmation="Phase24Strong123!")
        self.employee.refresh_from_db(); invitation.refresh_from_db()
        self.assertEqual(invitation.status, "accepted"); self.assertEqual(invitation.accepted_by, user)
        self.assertTrue(FirstLoginProgress.objects.filter(employee=self.employee).exists())
        self.assertEqual(account_status(self.employee), "REGISTRATION_IN_PROGRESS")
        progress = FirstLoginService.update(employee=self.employee, version=1, profile_completed=True, timezone_completed=True, visibility_completed=True)
        self.assertIsNotNone(progress.completed_at); self.assertEqual(account_status(self.employee), "ACTIVE")

    def test_public_validate_does_not_disclose_employee(self):
        _, raw = InvitationService.issue(employee=self.employee, actor_user=self.admin, delivery_address=self.employee.work_email)
        good = self.client.post("/api/public/v1/auth/invitations/validate/", {"token":raw}, content_type="application/json")
        bad = self.client.post("/api/public/v1/auth/invitations/validate/", {"token":"unknown"}, content_type="application/json")
        self.assertEqual(set(good.json()), {"valid","state"}); self.assertEqual(set(bad.json()), {"valid","state"})

    def test_template_publish_is_versioned_immutable_and_rejects_cycle(self):
        template = self.template(); version = template.published_version
        self.assertEqual(version.steps.count(), 1)
        template.name="Changed draft name"; template.save(update_fields=["name"])
        version.refresh_from_db(); self.assertEqual(version.name_snapshot, "Базовый")
        other=OnboardingTemplateService.create(actor_user=self.admin,name="Cycle")
        with self.assertRaises(ValidationError):
            OnboardingTemplateService.publish(template=other,actor_user=self.admin,expected_version=1,steps=[{"key":"a","title":"A","step_type":"manual","dependencies":["b"]},{"key":"b","title":"B","step_type":"manual","dependencies":["a"]}])

    def test_assignment_dependency_completion_and_snapshot(self):
        template=self.template([
            {"key":"one","title":"Первый","step_type":"manual","required":True,"responsible_strategy":"self"},
            {"key":"two","title":"Второй","step_type":"manual","required":True,"responsible_strategy":"self","dependencies":["one"]},
        ])
        instance=OnboardingService.assign(employee=self.employee,actor_user=self.admin,template=template)
        steps=list(instance.steps.order_by("template_step__position")); self.assertEqual([x.status for x in steps],["pending","blocked"])
        OnboardingService.step_action(step=steps[0],actor_employee=self.employee,actor_user=self.admin,expected_version=1,action="complete")
        steps[1].refresh_from_db(); self.assertEqual(steps[1].status,"pending")
        OnboardingService.step_action(step=steps[1],actor_employee=self.employee,actor_user=self.admin,expected_version=1,action="complete")
        instance.refresh_from_db(); self.assertEqual(instance.status,"completed"); self.assertEqual(instance.progress_percent,100)
        self.assertTrue(AuditEvent.objects.filter(action="people.onboarding.completed").exists()); self.assertTrue(OutboxEvent.objects.filter(event_type="people.onboarding.completed").exists())

    def test_optimistic_lock_and_termination_cancel(self):
        instance=OnboardingService.assign(employee=self.employee,actor_user=self.admin,template=self.template())
        with self.assertRaises(OnboardingConflict): OnboardingService.transition(instance=instance,actor_user=self.admin,expected_version=99,action="start")
        EmployeeService.terminate(employee=self.employee,actor_user=self.admin)
        instance.refresh_from_db(); self.employee.refresh_from_db(); self.assertEqual(instance.status,"cancelled"); self.assertEqual(account_status(self.employee),"TERMINATED")
        EmployeeService.reactivate(employee=self.employee,actor_user=self.admin); self.employee.refresh_from_db()
        self.assertFalse(self.employee.user.is_active) if self.employee.user_id else None

    def test_audit_failure_rolls_back_assignment(self):
        from unittest.mock import patch
        template=self.template(); before=OnboardingInstance.objects.count()
        with patch("employees.onboarding_lifecycle.AuditService.record",side_effect=RuntimeError("audit unavailable")):
            with self.assertRaises(RuntimeError):OnboardingService.assign(employee=self.employee,actor_user=self.admin,template=template)
        self.assertEqual(OnboardingInstance.objects.count(),before)

    def test_task_step_creates_one_production_task(self):
        from work_tasks.models import TaskTemplate
        target=AssignmentTarget.objects.create(target_type="employee",employee=self.employee)
        task_template=TaskTemplate.objects.create(name="Welcome",task_title="Welcome task",responsible_target=target,created_by=self.employee)
        template=self.template([{"key":"task","title":"Task","step_type":"task","task_template":task_template,"responsible_strategy":"self"}])
        instance=OnboardingService.assign(employee=self.employee,actor_user=self.admin,template=template);step=instance.steps.get()
        first=OnboardingService.create_task(step=step,actor_employee=self.employee,actor_user=self.admin)
        second=OnboardingService.create_task(step=step,actor_employee=self.employee,actor_user=self.admin)
        self.assertEqual(first.pk,second.pk);self.assertEqual(first.onboarding_step.pk,step.pk)

    def test_rehire_requires_invitation_and_reuses_same_user(self):
        _,raw=InvitationService.issue(employee=self.employee,actor_user=self.admin,delivery_address=self.employee.work_email)
        user=InvitationService.activate(token=raw,password="Phase24Strong123!",password_confirmation="Phase24Strong123!")
        EmployeeService.terminate(employee=self.employee,actor_user=self.admin);EmployeeService.reactivate(employee=self.employee,actor_user=self.admin);self.employee.refresh_from_db()
        self.assertFalse(user.__class__.objects.get(pk=user.pk).is_active);self.assertEqual(account_status(self.employee),"REACTIVATION_REQUIRED")
        _,new_raw=InvitationService.issue(employee=self.employee,actor_user=self.admin,delivery_address=self.employee.work_email)
        restored=InvitationService.activate(token=new_raw,password="Phase24Restored123!",password_confirmation="Phase24Restored123!")
        self.employee.refresh_from_db();self.assertEqual(restored.pk,user.pk);self.assertEqual(self.employee.employee_number,"P24-1");self.assertEqual(account_status(self.employee),"REGISTRATION_IN_PROGRESS")


class Phase24ConcurrencyTests(TransactionTestCase):
    reset_sequences=True
    def setUp(self):
        self.admin=get_user_model().objects.create_superuser(username="p24-concurrency",email="p24-concurrency@example.test",password="StrongAdmin123!")
        self.employee=Employee.objects.create(first_name="Parallel",employee_number="P24-C")
        self.template=OnboardingTemplateService.create(actor_user=self.admin,name="Parallel template")
        OnboardingTemplateService.publish(template=self.template,actor_user=self.admin,expected_version=1,steps=[{"key":"one","title":"One","step_type":"manual","responsible_strategy":"self"}]);self.template.refresh_from_db()

    def assign(self):
        close_old_connections()
        try: OnboardingService.assign(employee=Employee.objects.get(pk=self.employee.pk),actor_user=self.admin,template=OnboardingTemplate.objects.get(pk=self.template.pk));return True
        except Exception:return False
        finally:connections.close_all()

    def test_parallel_assignment_creates_one_active_instance(self):
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:self.assign(),range(2)))
        self.assertEqual(results.count(True),1);self.assertEqual(OnboardingInstance.objects.filter(employee=self.employee,status__in=["pending","active","paused"]).count(),1)

    def complete(self,step_id):
        close_old_connections()
        try:
            from .models import OnboardingStepInstance
            OnboardingService.step_action(step=OnboardingStepInstance.objects.get(pk=step_id),actor_employee=Employee.objects.get(pk=self.employee.pk),actor_user=self.admin,expected_version=1,action="complete");return True
        except Exception:return False
        finally:connections.close_all()

    def test_parallel_step_completion_is_single_winner(self):
        instance=OnboardingService.assign(employee=self.employee,actor_user=self.admin,template=self.template);step=instance.steps.get()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:self.complete(step.pk),range(2)))
        self.assertEqual(results.count(True),1)

    def test_accept_racing_revoke_never_accepts_revoked_invitation(self):
        invitation,raw=InvitationService.issue(employee=self.employee,actor_user=self.admin,delivery_address="race@example.test")
        def accept():
            close_old_connections()
            try:InvitationService.activate(token=raw,password="RacePassword123!",password_confirmation="RacePassword123!");return "accepted"
            except Exception:return "conflict"
            finally:connections.close_all()
        def revoke():
            close_old_connections()
            try:InvitationService.revoke(invitation=invitation,actor_user=self.admin);return "revoked"
            except Exception:return "conflict"
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:results=[pool.submit(accept),pool.submit(revoke)];results=[x.result() for x in results]
        invitation.refresh_from_db();self.assertFalse(invitation.used_at and invitation.revoked_at);self.assertEqual(sum(x in {"accepted","revoked"} for x in results),1)

    def test_accept_racing_termination_cannot_activate_terminated_employee(self):
        _,raw=InvitationService.issue(employee=self.employee,actor_user=self.admin,delivery_address="terminate-race@example.test")
        def accept():
            close_old_connections()
            try:InvitationService.activate(token=raw,password="RacePassword123!",password_confirmation="RacePassword123!")
            except Exception:pass
            finally:connections.close_all()
        def terminate():
            close_old_connections()
            try:EmployeeService.terminate(employee=Employee.objects.get(pk=self.employee.pk),actor_user=self.admin)
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(lambda fn:fn(),[accept,terminate]))
        self.employee.refresh_from_db();self.assertEqual(self.employee.status,"terminated");self.assertFalse(self.employee.is_active)
        if self.employee.user_id:self.assertFalse(get_user_model().objects.get(pk=self.employee.user_id).is_active)

    def test_complete_racing_skip_has_one_final_transition(self):
        instance=OnboardingService.assign(employee=self.employee,actor_user=self.admin,template=self.template);step=instance.steps.get()
        def run(action):
            close_old_connections()
            try:
                from .models import OnboardingStepInstance
                OnboardingService.step_action(step=OnboardingStepInstance.objects.get(pk=step.pk),actor_employee=Employee.objects.get(pk=self.employee.pk),actor_user=self.admin,expected_version=1,action=action,reason="approved skip",allow_skip=True);return True
            except Exception:return False
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,["complete","skip"]))
        self.assertEqual(results.count(True),1);step.refresh_from_db();self.assertIn(step.status,{"completed","skipped"})

    def test_parallel_task_step_creation_reuses_one_task(self):
        from work_tasks.models import TaskTemplate
        target=AssignmentTarget.objects.create(target_type="employee",employee=self.employee)
        task_template=TaskTemplate.objects.create(name="Parallel",task_title="Parallel",responsible_target=target,created_by=self.employee)
        template=OnboardingTemplateService.create(actor_user=self.admin,name="Task parallel")
        OnboardingTemplateService.publish(template=template,actor_user=self.admin,expected_version=1,steps=[{"key":"task","title":"Task","step_type":"task","task_template":task_template,"responsible_strategy":"self"}]);template.refresh_from_db()
        step=OnboardingService.assign(employee=self.employee,actor_user=self.admin,template=template).steps.get()
        def create():
            close_old_connections()
            try:
                from .models import OnboardingStepInstance
                return str(OnboardingService.create_task(step=OnboardingStepInstance.objects.get(pk=step.pk),actor_employee=Employee.objects.get(pk=self.employee.pk),actor_user=self.admin).pk)
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:ids=list(pool.map(lambda _:create(),range(2)))
        self.assertEqual(len(set(ids)),1)

    def test_suspend_restore_race_is_consistent(self):
        from .services import AccountAccessService
        user=get_user_model().objects.create_user(username="access-race",email="access-race@example.test",password="StrongAccess123!");self.employee.user=user;self.employee.save(update_fields=["user"])
        def change(enabled,action):
            close_old_connections()
            try:AccountAccessService.set_access(employee=Employee.objects.get(pk=self.employee.pk),actor_user=self.admin,enabled=enabled,action=action);return True
            except Exception:return False
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(lambda args:change(*args),[(False,"suspended"),(True,"restored")]))
        self.employee.refresh_from_db();user.refresh_from_db();self.assertEqual(user.is_active,self.employee.account_access_state=="normal")

    def test_termination_racing_completion_leaves_cancelled_or_completed_history(self):
        instance=OnboardingService.assign(employee=self.employee,actor_user=self.admin,template=self.template);step=instance.steps.get()
        def complete():
            close_old_connections()
            try:
                from .models import OnboardingStepInstance
                OnboardingService.step_action(step=OnboardingStepInstance.objects.get(pk=step.pk),actor_employee=Employee.objects.get(pk=self.employee.pk),actor_user=self.admin,expected_version=1,action="complete")
            except Exception:pass
            finally:connections.close_all()
        def terminate():
            close_old_connections()
            try:EmployeeService.terminate(employee=Employee.objects.get(pk=self.employee.pk),actor_user=self.admin)
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(lambda fn:fn(),[complete,terminate]))
        instance.refresh_from_db();self.employee.refresh_from_db();self.assertEqual(self.employee.status,"terminated");self.assertIn(instance.status,{"cancelled","completed"})
