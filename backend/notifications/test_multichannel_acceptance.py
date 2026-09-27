from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.core import mail
from django.db import close_old_connections, connection, connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from .channels import EmailChannelHandler, ProviderFailure
from .models import Notification, NotificationDelivery, NotificationIntent, NotificationPreference
from .services import ingest_event, process_deliveries
from .test_core import event, fixture


def reason_event(employee, reason, index):
    source=event(employee)
    payload={**source.payload,'reason':reason}
    if reason in {'WORK_TASK_REOPENED','WORK_TASK_REJECTED'}:
        from access_control.models import EmployeeRole, Permission, Role, RolePermission
        from work_tasks.models import Task
        permission,_=Permission.objects.get_or_create(code='task.view',defaults={'name':'View Work tasks'})
        role=Role.objects.create(code=f'notify-work-{reason.lower()}-{index}',name='Synthetic Work notification')
        RolePermission.objects.create(role=role,permission=permission,scope='own')
        EmployeeRole.objects.create(employee=employee,role=role)
        task=Task.objects.create(number=f'TASK-NOTIFY-{index}-{reason[-3:]}',title='Synthetic closed Work task',
            author=employee,executor_employee=employee,created_by=employee.user,updated_by=employee.user)
        payload.update(task_id=str(task.pk),task_number=task.number)
    source.payload=payload;source.save(update_fields=['payload'])
    return source


@override_settings(NOTIFICATIONS_EMAIL_ENABLED=True, NOTIFICATIONS_TELEGRAM_ENABLED=False,
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class MultichannelAcceptanceTests(TestCase):
    def test_work_notification_is_hidden_and_delivery_suppressed_after_task_access_revocation(self):
        from access_control.models import RolePermission
        user,employee=fixture('work-revoked')
        source=reason_event(employee,'WORK_TASK_REOPENED',99)
        ingest_event(source)
        item=Notification.objects.get(intent__source_event_id=source.event_id)
        RolePermission.objects.filter(role__employee_assignments__employee=employee,
            permission__code='task.view').delete()
        client=APIClient();client.force_authenticate(user)
        self.assertEqual(client.get('/api/v1/notifications/').data['count'],0)
        self.assertEqual(client.get('/api/v1/notifications/unread-count/').data['count'],0)
        process_deliveries()
        self.assertFalse(item.deliveries.filter(status='delivered').exists())
        self.assertTrue(item.deliveries.filter(last_error_code='TASK_ACCESS_REVOKED').exists())

    def test_people_reasons_respect_email_preferences_without_suppressing_in_app(self):
        for index,reason in enumerate(['WORK_TASK_REOPENED','WORK_TASK_REJECTED','PEOPLE_INVITATION_EXPIRED','PEOPLE_STEP_OVERDUE']):
            _,employee=fixture('people-pref-'+str(index))
            NotificationPreference.objects.create(employee=employee,reason=reason,channel='email',enabled=False)
            source=reason_event(employee,reason,index)
            ingest_event(source);process_deliveries()
            item=Notification.objects.get(intent__source_event_id=source.event_id)
            self.assertEqual(item.deliveries.get(channel='email').last_error_code,'PREFERENCE_DISABLED')
            self.assertEqual(item.deliveries.get(channel='email').attempt_log.count(),0)
            self.assertEqual(item.deliveries.get(channel='in_app').status,'delivered')
        self.assertEqual(len(mail.outbox),0)

    def test_people_reasons_respect_quiet_hours_without_delaying_in_app(self):
        from .models import NotificationQuietHours
        for index,reason in enumerate(['WORK_TASK_REOPENED','WORK_TASK_REJECTED','PEOPLE_INVITATION_EXPIRED','PEOPLE_STEP_OVERDUE']):
            _,employee=fixture('people-quiet-'+str(index))
            now=timezone.now()
            NotificationQuietHours.objects.create(employee=employee,enabled=True,timezone='UTC',
                starts_at=(now-timedelta(hours=1)).time(),ends_at=(now+timedelta(hours=1)).time())
            source=reason_event(employee,reason,index)
            ingest_event(source);process_deliveries()
            item=Notification.objects.get(intent__source_event_id=source.event_id)
            delivery=item.deliveries.get(channel='email')
            self.assertEqual(delivery.status,'pending')
            self.assertGreater(delivery.next_attempt_at,now)
            self.assertEqual(delivery.attempt_log.count(),0)
            self.assertEqual(item.deliveries.get(channel='in_app').status,'delivered')
        self.assertEqual(len(mail.outbox),0)

    def test_reconciliation_old_materialized_events_do_not_starve_new_events(self):
        from .services import ingest_pending
        _,employee=fixture('starvation')
        old=event(employee);ingest_event(old)
        old.status='processed';old.save(update_fields=['status'])
        fresh=event(employee)
        self.assertEqual(ingest_pending(batch_size=1,reconcile=True),1)
        self.assertTrue(NotificationIntent.objects.filter(source_event_id=fresh.event_id,status='materialized').exists())

    def assert_contract(self, source, employee, email_enabled=True):
        intent = NotificationIntent.objects.get(source_event_id=source.event_id)
        self.assertEqual(intent.status, 'materialized')
        self.assertEqual(intent.reason, 'SLA_ESCALATION')
        item = Notification.objects.get(intent=intent)
        self.assertEqual(item.recipient_id, employee.user_id)
        self.assertEqual(item.recipient_employee_id, employee.pk)
        self.assertEqual(item.entity_id, '42')
        self.assertEqual(item.priority, 'critical')
        self.assertIn('42', item.title)
        self.assertIn('2', item.message)
        deliveries = {d.channel: d for d in item.deliveries.all()}
        self.assertEqual(set(deliveries), {'in_app', 'email', 'telegram'})
        self.assertEqual(deliveries['telegram'].status, 'suppressed')
        self.assertEqual(deliveries['telegram'].attempt_log.count(), 0)
        for channel in ['in_app', 'email']:
            delivery = deliveries[channel]
            enabled = channel == 'in_app' or email_enabled
            self.assertEqual(delivery.status, 'delivered' if enabled else 'suppressed')
            self.assertEqual(delivery.attempt_log.count(), int(enabled))
            if enabled:
                self.assertTrue(delivery.attempt_log.get().successful)
                self.assertEqual(delivery.attempt_log.get().attempt_number, 1)
            else:
                self.assertEqual(delivery.last_error_code, 'CHANNEL_DISABLED')
        return item

    def test_email_enabled_one_logical_notification_one_delivery_per_channel(self):
        _, employee = fixture('multi')
        source = event(employee)
        self.assertFalse(NotificationPreference.objects.filter(employee=employee).exists())
        ingest_event(source)
        process_deliveries()
        item = self.assert_contract(source, employee)
        self.assertFalse(item.is_read)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [employee.user.email])
        self.assertIn('42', mail.outbox[0].subject)
        self.assertIn('breach', mail.outbox[0].body)
        before = list(item.deliveries.order_by('pk').values_list('pk', flat=True))
        ingest_event(source)
        process_deliveries()
        self.assertEqual(NotificationIntent.objects.count(), 1)
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(list(item.deliveries.order_by('pk').values_list('pk', flat=True)), before)
        self.assert_contract(source, employee)
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(NOTIFICATIONS_EMAIL_ENABLED=False)
    def test_email_disabled_is_suppressed_not_an_attempt(self):
        _, employee = fixture('off')
        source = event(employee)
        ingest_event(source)
        process_deliveries()
        ingest_event(source)
        process_deliveries()
        self.assert_contract(source, employee, email_enabled=False)
        self.assertEqual(len(mail.outbox), 0)

    def test_email_preference_does_not_suppress_mandatory_in_app(self):
        _, employee = fixture('pref')
        for channel in ['in_app', 'email']:
            NotificationPreference.objects.create(employee=employee, reason='SLA_ESCALATION', channel=channel, enabled=False)
        ingest_event(event(employee))
        process_deliveries()
        self.assertEqual(NotificationDelivery.objects.get(channel='email').last_error_code, 'PREFERENCE_DISABLED')
        self.assertEqual(NotificationDelivery.objects.get(channel='in_app').status, 'delivered')
        self.assertEqual(len(mail.outbox), 0)

    def test_email_retry_does_not_repeat_successful_in_app(self):
        _, employee = fixture('retry')
        source = event(employee)
        ingest_event(source)
        with patch.object(EmailChannelHandler, 'send', side_effect=ProviderFailure('TEST_RETRY', retryable=True)):
            process_deliveries()
        app = NotificationDelivery.objects.get(channel='in_app')
        email = NotificationDelivery.objects.get(channel='email')
        self.assertEqual(app.status, 'delivered')
        self.assertEqual(email.status, 'retry')
        self.assertEqual(app.attempt_log.count(), 1)
        self.assertEqual(email.attempt_log.get().outcome, 'retry')
        ingest_event(source)
        NotificationDelivery.objects.filter(pk=email.pk).update(next_attempt_at=timezone.now()-timedelta(seconds=1))
        process_deliveries()
        process_deliveries()
        email.refresh_from_db()
        self.assertEqual(email.status, 'delivered')
        self.assertEqual(email.attempt_log.count(), 2)
        self.assertEqual(app.attempt_log.count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [employee.user.email])
        self.assertEqual(Notification.objects.count(), 1)


@override_settings(NOTIFICATIONS_EMAIL_ENABLED=True, NOTIFICATIONS_TELEGRAM_ENABLED=False,
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class MultichannelConcurrencyTests(TransactionTestCase):
    @skipUnless(connection.vendor == 'postgresql', 'PostgreSQL locking required')
    def test_workers_claim_each_enabled_channel_once(self):
        _, employee = fixture('parallel')
        source = event(employee)
        ingest_event(source)
        barrier = Barrier(4, timeout=10)
        def run(_):
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '5s'")
                    cursor.execute("SET statement_timeout = '10s'")
                barrier.wait()
                return process_deliveries(3)
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(run, n) for n in range(4)]
            self.assertEqual(sum(f.result(timeout=30) for f in futures), 2)
        ingest_event(source)
        self.assertEqual(process_deliveries(), 0)
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(NotificationIntent.objects.count(), 1)
        for channel in ['in_app', 'email']:
            delivery = NotificationDelivery.objects.get(channel=channel)
            self.assertEqual(delivery.status, 'delivered')
            self.assertEqual(delivery.attempt_log.count(), 1)
            self.assertTrue(delivery.attempt_log.get().successful)
        self.assertEqual(NotificationDelivery.objects.get(channel='telegram').attempt_log.count(), 0)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [employee.user.email])
