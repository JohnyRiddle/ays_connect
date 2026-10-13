import hashlib
from datetime import timedelta
from django.test import TestCase, TransactionTestCase, override_settings
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient
from work_tasks import test_task_patch as fixtures
from work_tasks.services import TaskService
from work_tasks.collaboration import CollaborationService
from events.models import OutboxEvent
from .models import TelegramAccount, NotificationDelivery, NotificationDeliveryAttempt, Notification
from .services import ingest_event, process_deliveries
from .linking import TelegramLinkService
from .bot_api import reconcile_leases

SERVICE_TOKEN = 'synthetic-only-contract-key'
ROOT = '/api/integrations/corporate-telegram/v1/'


@override_settings(TELEGRAM_BOT_SERVICE_ENABLED=True, TELEGRAM_BOT_SERVICE_TOKEN_SHA256=hashlib.sha256(SERVICE_TOKEN.encode()).hexdigest(), TELEGRAM_DELIVERY_TRANSPORT='pull', NOTIFICATIONS_TELEGRAM_ENABLED=True)
class BotContractTests(TestCase):
    def setUp(self):
        fixtures.TaskPatchTests.setUp(self)
        cache.clear()
        self.client = APIClient(); self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + SERVICE_TOKEN)
        self.task = TaskService.create(actor=self.author, actor_user=self.admin, title='Synthetic bot task', responsible_department=self.unit)
        self.account = TelegramAccount.objects.create(employee=self.head, telegram_user_id=10001, telegram_chat_id=10001, linked_at=timezone.now())
        ingest_event(OutboxEvent.objects.get(event_type='task.created', entity_id=str(self.task.pk)))

    def claim(self):
        response = self.client.post(ROOT + 'deliveries/claim/', {}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        return response.data['results']

    def command(self, item, name, **data):
        return self.client.post(ROOT + f"deliveries/{item['delivery_id']}/{name}/", {'lease_token': item['lease_token'], **data}, format='json')

    def test_claim_is_exclusive_begin_ack_are_idempotent_and_record_message_id(self):
        item = self.claim()[0]
        self.assertEqual(self.claim(), [])
        self.assertIn('event_id', item); self.assertEqual(item['telegram_chat_id'], 10001)
        self.assertTrue(self.command(item, 'begin').data['send_allowed'])
        self.assertFalse(self.command(item, 'begin').data['send_allowed'])
        self.assertEqual(self.command(item, 'ack', telegram_message_id='synthetic-77').data['status'], 'delivered')
        self.assertEqual(self.command(item, 'ack', telegram_message_id='synthetic-77').status_code, 200)
        self.assertEqual(self.command(item, 'ack', telegram_message_id='different').status_code, 400)
        delivery = NotificationDelivery.objects.get(pk=item['delivery_id'])
        self.assertEqual(delivery.provider_message_id, 'synthetic-77')
        self.assertEqual(delivery.attempt_log.count(), 1)

    def test_expired_reservation_before_begin_is_safe_to_reclaim_old_token_rejected(self):
        old = self.claim()[0]
        NotificationDelivery.objects.filter(pk=old['delivery_id']).update(lease_expires_at=timezone.now()-timedelta(seconds=1))
        new = self.claim()[0]
        self.assertNotEqual(old['lease_token'], new['lease_token'])
        self.assertEqual(self.command(old, 'begin').status_code, 400)

    def test_expired_after_begin_is_unknown_and_never_automatically_reissued(self):
        item = self.claim()[0]; self.command(item, 'begin')
        NotificationDelivery.objects.filter(pk=item['delivery_id']).update(lease_expires_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(self.claim(), [])
        self.assertEqual(NotificationDelivery.objects.get(pk=item['delivery_id']).status, 'unknown')
        self.assertEqual(self.command(item, 'ack', telegram_message_id='synthetic-late').data['status'], 'delivered')

    def test_ambiguous_failure_is_terminal_and_blocked_account_is_visible(self):
        item = self.claim()[0]; self.command(item, 'begin')
        response = self.command(item, 'fail', category='ambiguous')
        self.assertEqual(response.data['status'], 'unknown'); self.assertEqual(self.claim(), [])
        self.assertEqual(self.command(item, 'fail', category='ambiguous').status_code, 200)

    def test_bot_block_failure_disables_delivery_and_status_exposes_it(self):
        item = self.claim()[0]; self.command(item, 'begin')
        self.assertEqual(self.command(item, 'fail', category='blocked').data['status'], 'failed')
        profile = APIClient(); profile.force_authenticate(self.head_user)
        response = profile.get('/api/internal/v1/notification-channels/telegram/')
        self.assertTrue(response.data['blocked']); self.assertEqual(response.data['last_delivery']['error_code'], 'blocked')

    def test_retryable_failure_is_bounded_and_can_be_reclaimed_after_backoff(self):
        item = self.claim()[0]; self.command(item, 'begin')
        self.assertEqual(self.command(item, 'fail', category='retryable').data['status'], 'retry')
        self.assertEqual(self.claim(), [])
        NotificationDelivery.objects.filter(pk=item['delivery_id']).update(next_attempt_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(len(self.claim()), 1)

    def test_access_revocation_before_claim_or_begin_suppresses_packets(self):
        item = self.claim()[0]
        from access_control.models import EmployeeRole
        EmployeeRole.objects.filter(employee=self.head).update(is_active=False)
        response = self.command(item, 'begin')
        self.assertFalse(response.data['send_allowed'])
        delivery = NotificationDelivery.objects.get(pk=item['delivery_id']); self.assertEqual(delivery.last_error_code, 'TASK_ACCESS_REVOKED')

    def test_inactive_employee_gets_no_packet(self):
        self.head.is_active = False; self.head.save()
        self.assertEqual(self.claim(), [])

    def test_binding_revoke_after_claim_blocks_begin(self):
        item = self.claim()[0]
        TelegramLinkService.unlink(self.head, self.head_user)
        self.assertFalse(self.command(item, 'begin').data['send_allowed'])

    def test_account_linking_redeems_once_private_only_and_rejects_foreign_transfer(self):
        raw, token = TelegramLinkService.issue(self.member, self.member_user)
        payload = {'code': raw, 'telegram_user_id': 10002, 'private_chat_id': 10002, 'username': 'synthetic_only'}
        self.assertEqual(self.client.post(ROOT+'bindings/redeem/', payload, format='json').status_code, 200)
        self.assertEqual(self.client.post(ROOT+'bindings/redeem/', payload, format='json').status_code, 400)
        raw, _ = TelegramLinkService.issue(self.other, self.other_user)
        self.assertEqual(self.client.post(ROOT+'bindings/redeem/', dict(payload, code=raw), format='json').status_code, 400)
        raw, _ = TelegramLinkService.issue(self.member, self.member_user)
        self.assertEqual(self.client.post(ROOT+'bindings/redeem/', dict(payload, code=raw, private_chat_id=-100), format='json').status_code, 400)

    def test_expired_code_and_deactivated_employee_are_rejected(self):
        raw, token = TelegramLinkService.issue(self.member, self.member_user)
        token.expires_at = timezone.now()-timedelta(seconds=1); token.save()
        payload = {'code': raw, 'telegram_user_id': 10002, 'private_chat_id': 10002}
        self.assertEqual(self.client.post(ROOT+'bindings/redeem/', payload, format='json').status_code, 400)
        raw, token = TelegramLinkService.issue(self.member, self.member_user)
        self.member.is_active = False; self.member.save()
        self.assertEqual(self.client.post(ROOT+'bindings/redeem/', dict(payload, code=raw), format='json').status_code, 400)

    def test_service_key_cannot_read_employee_task_attachment_or_grants_apis(self):
        for path in ['/employees/', '/tasks/', '/roles/', f'/tasks/{self.task.pk}/attachments/']:
            self.assertEqual(self.client.get('/api/internal/v1'+path).status_code, 401)
        self.client.credentials()
        self.assertEqual(self.client.post(ROOT+'deliveries/claim/', {}, format='json').status_code, 401)

    def test_revocation_and_rotation_of_credentials(self):
        with override_settings(TELEGRAM_BOT_SERVICE_ENABLED=False):
            self.assertEqual(self.client.post(ROOT+'deliveries/claim/', {}, format='json').status_code, 401)
        with override_settings(TELEGRAM_BOT_SERVICE_TOKEN_SHA256='different', TELEGRAM_BOT_SERVICE_PREVIOUS_TOKEN_SHA256=hashlib.sha256(SERVICE_TOKEN.encode()).hexdigest()):
            self.assertEqual(self.client.post(ROOT+'deliveries/claim/', {}, format='json').status_code, 200)

    def test_internal_comment_is_not_notified_to_non_internal_participant(self):
        comment = CollaborationService.add_comment(task=self.task, actor=self.author, actor_user=self.admin, body='Internal synthetic secret', is_internal=True)
        ingest_event(OutboxEvent.objects.get(event_type='task.comment_added', entity_id=str(comment.pk)))
        self.assertEqual(Notification.objects.filter(recipient_employee=self.head).count(), 1)

    def test_background_sender_does_not_take_bot_deliveries(self):
        process_deliveries()
        item = self.claim()[0]
        self.assertEqual(NotificationDelivery.objects.get(pk=item['delivery_id']).status, 'processing')


@override_settings(TELEGRAM_BOT_SERVICE_ENABLED=True, TELEGRAM_BOT_SERVICE_TOKEN_SHA256=hashlib.sha256(SERVICE_TOKEN.encode()).hexdigest(), TELEGRAM_DELIVERY_TRANSPORT='pull', NOTIFICATIONS_TELEGRAM_ENABLED=True)
class BotConcurrencyTests(TransactionTestCase):
    setUp = BotContractTests.setUp

    def race(self, function):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections, connections
        barrier = Barrier(2)
        def call():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return function()
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(lambda _: call(), range(2)))

    def test_concurrent_claims_reserve_each_delivery_once(self):
        def claim():
            client = APIClient(); client.credentials(HTTP_AUTHORIZATION='Bearer '+SERVICE_TOKEN)
            response = client.post(ROOT+'deliveries/claim/', {}, format='json')
            self.assertEqual(response.status_code, 200, response.data)
            return len(response.data['results'])
        self.assertEqual(sum(self.race(claim)), 1)

    def test_concurrent_redemption_of_one_code_has_one_winner(self):
        raw, _ = TelegramLinkService.issue(self.member, self.member_user)
        def redeem():
            client = APIClient(); client.credentials(HTTP_AUTHORIZATION='Bearer '+SERVICE_TOKEN)
            return client.post(ROOT+'bindings/redeem/', {'code': raw, 'telegram_user_id': 10002, 'private_chat_id': 10002}, format='json').status_code
        self.assertCountEqual(self.race(redeem), [200, 400])
        self.assertEqual(TelegramAccount.objects.filter(employee=self.member, is_active=True).count(), 1)
