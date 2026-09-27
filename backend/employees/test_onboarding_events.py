from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from events.models import OutboxEvent
from events.services import DomainEventService
from audit.models import AuditEvent
from work_tasks.models import Task, TaskTemplate
from access_control.models import EmployeeRole, Permission, Role, RolePermission
from .models import Employee, AssignmentTarget
from .onboarding_lifecycle import OnboardingService, OnboardingTemplateService
from .onboarding_events import consume, notify_overdue


@override_settings(NOTIFICATIONS_EMAIL_ENABLED=True, NOTIFICATIONS_TELEGRAM_ENABLED=False)
class OnboardingEventTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user(username='event-test',email='event-test@example.test')
        self.employee=Employee.objects.create(user=self.user,first_name='Synthetic')
        permission,_=Permission.objects.get_or_create(code='task.view',defaults={'name':'View Work tasks'})
        role=Role.objects.create(code='onboarding-event-task-reader',name='Synthetic task reader')
        RolePermission.objects.create(role=role,permission=permission,scope='own')
        EmployeeRole.objects.create(employee=self.employee,role=role)
        target=AssignmentTarget.objects.create(target_type='employee',employee=self.employee)
        work=TaskTemplate.objects.create(name='Event fixture',task_title='Task',responsible_target=target,created_by=self.employee)
        template=OnboardingTemplateService.create(actor_user=self.user,name='Event fixture')
        OnboardingTemplateService.publish(template=template,actor_user=self.user,expected_version=1,
            steps=[{'key':'task','title':'Required task','step_type':'task','task_template':work}])
        template.refresh_from_db()
        self.instance=OnboardingService.assign(employee=self.employee,actor_user=self.user,template=template)
        self.step=self.instance.steps.get()
        self.task=Task.objects.create(number='TASK-EVENT',title='Synthetic',author=self.employee,
            executor_employee=self.employee,created_by=self.user,updated_by=self.user,status='completed',completed_at=timezone.now())
        self.step.task=self.task;self.step.save(update_fields=['task'])
        OnboardingService.reconcile(self.instance)
        self.step.refresh_from_db();self.instance.refresh_from_db()

    def source(self, kind='task.reopened', version=2):
        Task.objects.filter(pk=self.task.pk).update(status='in_progress',completed_at=None,version=version)
        return DomainEventService.publish(event_type=kind,entity=self.task,actor=self.user,
            payload={'task_version':version,'actor_id':str(self.employee.pk),'reason':'Synthetic return'})

    def test_reopen_reactivates_completed_instance_and_preserves_audit_once(self):
        source=self.source();self.assertTrue(consume(source.pk));self.assertFalse(consume(source.pk))
        self.step.refresh_from_db();self.instance.refresh_from_db()
        self.assertEqual(self.step.status,'in_progress');self.assertEqual(self.instance.status,'active')
        self.assertEqual(self.instance.progress_percent,0);self.assertEqual(Task.objects.count(),1)
        record=AuditEvent.objects.get(action='people.onboarding.step_reopened')
        self.assertEqual(record.actor_id,self.user.pk);self.assertTrue(record.old_values['completed_at'])
        notifications=OutboxEvent.objects.filter(event_type='notification.requested')
        self.assertEqual(notifications.count(),1)
        from notifications.services import ingest_event
        from notifications.models import Notification
        ingest_event(notifications.get());notice=Notification.objects.get()
        self.assertEqual(notice.title,'Задача возвращена в работу')
        self.assertIn('Synthetic return',notice.message)
        self.assertEqual(set(notice.deliveries.values_list('channel',flat=True)),{'in_app','email'})

    def test_delayed_reopen_does_not_undo_later_completion(self):
        source=self.source()
        Task.objects.filter(pk=self.task.pk).update(status='completed',version=3,completed_at=timezone.now())
        consume(source.pk);self.step.refresh_from_db();self.instance.refresh_from_db()
        self.assertEqual(self.step.status,'completed');self.assertEqual(self.instance.status,'completed')
        self.assertFalse(OutboxEvent.objects.filter(event_type='notification.requested').exists())

    def test_reopen_followed_by_edit_still_reopens_step(self):
        source=self.source()
        Task.objects.filter(pk=self.task.pk).update(version=3)
        consume(source.pk);self.step.refresh_from_db()
        self.assertEqual(self.step.status,'in_progress')

    def test_competing_onboarding_is_preserved_with_diagnostic(self):
        from .models import OnboardingInstance
        from .onboarding_events import process_events
        from notifications.services import ingest_event
        from notifications.models import Notification
        source=self.source()
        other=OnboardingInstance.objects.create(employee=self.employee,template_version=self.instance.template_version,assigned_by=self.user)
        process_events();process_events();self.instance.refresh_from_db();other.refresh_from_db()
        self.assertEqual(self.instance.status,'completed');self.assertEqual(other.status,'pending')
        self.assertEqual(OutboxEvent.objects.filter(event_type='people.onboarding.reopen_blocked',causation_id=source.event_id).count(),1)
        self.assertEqual(AuditEvent.objects.filter(action='people.onboarding.reopen_blocked').count(),1)
        self.assertEqual(AuditEvent.objects.get(action='people.onboarding.reopen_blocked').actor_id,self.user.pk)
        notices=OutboxEvent.objects.filter(event_type='notification.requested',payload__reason='PEOPLE_ONBOARDING_REOPEN_BLOCKED')
        self.assertEqual(notices.count(),1)
        ingest_event(notices.get());ingest_event(notices.get())
        self.assertEqual(Notification.objects.count(),1)
        self.assertEqual(set(Notification.objects.get().deliveries.values_list('channel',flat=True)),{'in_app','email'})
        self.assertFalse(OutboxEvent.objects.filter(event_type='people.acceptance_event.handled',causation_id=source.event_id).exists())

    def test_authorized_cancel_of_b_then_retry_reopens_a(self):
        from .models import OnboardingInstance
        from .onboarding_events import process_events
        source=self.source()
        other=OnboardingInstance.objects.create(employee=self.employee,template_version=self.instance.template_version,assigned_by=self.user)
        process_events()
        OnboardingService.transition(instance=other,actor_user=self.user,expected_version=other.version,action='cancel',reason='Resolve competing onboarding')
        process_events();process_events()
        self.instance.refresh_from_db();other.refresh_from_db();self.step.refresh_from_db()
        self.assertEqual(other.status,'cancelled');self.assertEqual(self.instance.status,'active')
        self.assertEqual(self.step.status,'in_progress')
        self.assertEqual(AuditEvent.objects.filter(action='people.onboarding.cancelled').count(),1)
        self.assertEqual(AuditEvent.objects.filter(action='people.onboarding.step_reopened').count(),1)
        self.assertEqual(OutboxEvent.objects.filter(event_type='people.acceptance_event.handled',causation_id=source.event_id).count(),1)

    def test_active_and_paused_b_each_block_a_without_changing_b(self):
        from .models import OnboardingInstance
        for status in ('active','paused'):
            with self.subTest(status=status):
                other=OnboardingInstance.objects.create(employee=self.employee,template_version=self.instance.template_version,
                    assigned_by=self.user,status=status)
                source=self.source(version=2 if status=='active' else 3)
                self.assertFalse(consume(source.pk))
                self.instance.refresh_from_db();other.refresh_from_db()
                self.assertEqual(self.instance.status,'completed');self.assertEqual(other.status,status)
                self.assertEqual(OutboxEvent.objects.filter(event_type='people.onboarding.reopen_blocked',causation_id=source.event_id).count(),1)
                OnboardingService.transition(instance=other,actor_user=self.user,expected_version=other.version,action='cancel',reason='Synthetic cleanup')

    def test_blocked_audit_failure_rolls_back_diagnostic_and_notification(self):
        from .models import OnboardingInstance
        source=self.source()
        OnboardingInstance.objects.create(employee=self.employee,template_version=self.instance.template_version,assigned_by=self.user)
        with patch('employees.onboarding_events.AuditService.record',side_effect=RuntimeError('Synthetic')):
            with self.assertRaises(RuntimeError): consume(source.pk)
        self.instance.refresh_from_db();self.assertEqual(self.instance.status,'completed')
        self.assertFalse(OutboxEvent.objects.filter(causation_id=source.event_id).exists())

    def test_deactivation_between_materialization_and_delivery_suppresses(self):
        from notifications.services import ingest_event,process_deliveries
        from notifications.models import NotificationDeliveryAttempt,NotificationDelivery
        consume(self.source().pk)
        ingest_event(OutboxEvent.objects.get(event_type='notification.requested'))
        self.user.is_active=False;self.user.save(update_fields=['is_active'])
        process_deliveries()
        self.assertFalse(NotificationDeliveryAttempt.objects.exists())
        self.assertEqual(NotificationDelivery.objects.filter(last_error_code='RECIPIENT_INACTIVE',status='suppressed').count(),2)

    def test_cancelled_or_terminated_onboarding_is_not_reactivated(self):
        source=self.source();self.instance.status='cancelled';self.instance.save(update_fields=['status'])
        consume(source.pk);self.instance.refresh_from_db();self.assertEqual(self.instance.status,'cancelled')
        self.instance.status='completed';self.instance.save(update_fields=['status'])
        self.employee.status='terminated';self.employee.save(update_fields=['status'])
        consume(self.source(version=3).pk);self.instance.refresh_from_db();self.assertEqual(self.instance.status,'completed')

    def test_reopen_audit_failure_rolls_back_step_and_notification(self):
        source=self.source()
        with patch('employees.onboarding_events.AuditService.record',side_effect=RuntimeError('Synthetic')):
            with self.assertRaises(RuntimeError):consume(source.pk)
        self.step.refresh_from_db();self.assertEqual(self.step.status,'completed')
        self.assertFalse(OutboxEvent.objects.filter(causation_id=source.event_id).exists())

    def test_overdue_recipient_dedup_and_interval_and_resolved(self):
        self.instance.status='active';self.instance.save(update_fields=['status'])
        now=timezone.now();self.step.status='in_progress';self.step.due_at=now-timedelta(hours=1)
        self.step.save(update_fields=['status','due_at'])
        notify_overdue(self.instance,now);notify_overdue(self.instance,now)
        self.assertEqual(OutboxEvent.objects.filter(event_type='notification.requested').count(),1)
        notify_overdue(self.instance,now+timedelta(hours=24))
        self.assertEqual(OutboxEvent.objects.filter(event_type='notification.requested').count(),2)
        self.step.status='completed';self.step.save(update_fields=['status'])
        notify_overdue(self.instance,now+timedelta(hours=48))
        self.assertEqual(OutboxEvent.objects.filter(event_type='notification.requested').count(),2)

    def test_inactive_recipient_gets_diagnostic_not_notification(self):
        self.user.is_active=False;self.user.save(update_fields=['is_active'])
        consume(self.source().pk)
        self.assertFalse(OutboxEvent.objects.filter(event_type='notification.requested').exists())
        self.assertEqual(OutboxEvent.objects.filter(event_type='people.notification.no_recipient').count(),1)

    def test_reject_message_is_not_reopen_message(self):
        from notifications.services import ingest_event
        from notifications.models import Notification
        consume(self.source(kind='task.review_rejected').pk)
        ingest_event(OutboxEvent.objects.get(event_type='notification.requested'))
        self.assertEqual(Notification.objects.get().title,'Результат задачи отклонён')

    def test_expiry_creator_once_without_invitation_secret(self):
        from .onboarding import InvitationService
        from .models import EmployeeInvitation
        invited=Employee.objects.create(first_name='Invited')
        invitation,raw=InvitationService.issue(employee=invited,actor_user=self.user,delivery_address='invited@example.test')
        EmployeeInvitation.objects.filter(pk=invitation.pk).update(created_at=timezone.now()-timedelta(days=2),expires_at=timezone.now()-timedelta(days=1))
        from django.core.management import call_command
        call_command('process_onboarding');call_command('process_onboarding')
        rows=OutboxEvent.objects.filter(event_type='notification.requested',payload__reason='PEOPLE_INVITATION_EXPIRED')
        self.assertEqual(rows.count(),1);self.assertEqual(rows.get().payload['recipient_employee_id'],str(self.employee.pk))
        self.assertNotIn(raw,str(rows.get().payload));self.assertNotIn('token',str(rows.get().payload))


from django.test import TransactionTestCase
class OnboardingEventConcurrencyTests(TransactionTestCase):
    setUp=OnboardingEventTests.setUp
    source=OnboardingEventTests.source

    def test_parallel_overdue_workers_emit_once_per_recipient(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections, connections
        self.instance.status='active';self.instance.save(update_fields=['status'])
        now=timezone.now()
        self.step.status='in_progress';self.step.due_at=now-timedelta(hours=2)
        self.step.save(update_fields=['status','due_at'])
        barrier=Barrier(2)
        def run():
            close_old_connections()
            try:
                with connections['default'].cursor() as cursor:
                    cursor.execute("SET lock_timeout='5s'")
                    cursor.execute("SET statement_timeout='10s'")
                barrier.wait(timeout=10)
                notify_overdue(self.instance,now)
            finally:connections['default'].close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs=[pool.submit(run) for _ in range(2)]
            for job in jobs:job.result(timeout=30)
        self.assertEqual(OutboxEvent.objects.filter(event_type='notification.requested',payload__reason='PEOPLE_STEP_OVERDUE').count(),1)

    def test_two_workers_consume_transition_once(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections, connections
        source=self.source();barrier=Barrier(2)
        def run():
            close_old_connections()
            try:
                with connections['default'].cursor() as cursor:
                    cursor.execute("SET lock_timeout = '5s'")
                    cursor.execute("SET statement_timeout = '10s'")
                barrier.wait(timeout=10)
                return consume(source.pk)
            finally:connections['default'].close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs=[pool.submit(run) for _ in range(2)]
            results=[job.result(timeout=30) for job in jobs]
        self.assertEqual(sorted(results),[False,True])
        self.assertEqual(OutboxEvent.objects.filter(event_type='notification.requested').count(),1)
        self.assertEqual(AuditEvent.objects.filter(action='people.onboarding.step_reopened').count(),1)

    def test_assign_b_racing_reopen_a_keeps_one_active_instance(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections,connections
        from .models import OnboardingInstance
        from .onboarding_events import process_events
        source=self.source();barrier=Barrier(2)
        template=self.instance.template_version.template
        def run_assign():
            close_old_connections()
            try:
                with connections['default'].cursor() as cursor: cursor.execute("SET lock_timeout='5s'")
                barrier.wait(timeout=10)
                return OnboardingService.assign(employee=self.employee,actor_user=self.user,template=template).pk
            finally: connections['default'].close()
        def run_reopen():
            close_old_connections()
            try:
                with connections['default'].cursor() as cursor: cursor.execute("SET lock_timeout='5s'")
                barrier.wait(timeout=10)
                return consume(source.pk)
            finally: connections['default'].close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs=[pool.submit(run_assign),pool.submit(run_reopen)]
            outcomes=[]
            for job in jobs:
                try: outcomes.append(job.result(timeout=30))
                except Exception as exc: outcomes.append(type(exc).__name__)
        active=list(OnboardingInstance.objects.filter(employee=self.employee,status__in=['pending','active','paused']))
        self.assertEqual(len(active),1)
        self.instance.refresh_from_db()
        self.assertIn(self.instance.status, ['completed','active'])
        if self.instance.status=='active':
            self.assertIn('OnboardingConflict',outcomes)
        else:
            self.assertEqual(active[0].status,'pending')
            self.assertIn(False,outcomes)
        process_events()
        self.assertLessEqual(OutboxEvent.objects.filter(event_type='notification.requested',payload__reason='PEOPLE_ONBOARDING_REOPEN_BLOCKED').count(),1)
