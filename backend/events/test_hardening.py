from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from .models import OutboxEvent
from .services import MAX_OUTBOX_ATTEMPTS, OutboxProcessor


class OutboxHardeningTests(TestCase):
    def event(self): return OutboxEvent.objects.create(event_type="test",entity_type="Test",entity_id="1",occurred_at=timezone.now())

    def test_handler_error_is_sanitized_and_retry_scheduled(self):
        item=self.event()
        def handler(event): raise RuntimeError("password=do-not-store")
        OutboxProcessor.process_batch(handler); item.refresh_from_db()
        self.assertEqual(item.last_error_code,"RuntimeError"); self.assertNotIn("do-not-store",item.last_error); self.assertIsNotNone(item.next_attempt_at)

    def test_poison_event_becomes_terminal(self):
        item=self.event(); item.attempts=MAX_OUTBOX_ATTEMPTS-1; item.save(update_fields=("attempts",))
        OutboxProcessor.process_batch(lambda event: (_ for _ in ()).throw(ValueError("secret"))); item.refresh_from_db()
        self.assertEqual(item.attempts,MAX_OUTBOX_ATTEMPTS); self.assertIsNone(item.next_attempt_at)

    def test_terminal_event_requires_explicit_confirm_to_retry(self):
        item=self.event(); item.status=OutboxEvent.Status.FAILED; item.attempts=MAX_OUTBOX_ATTEMPTS; item.save()
        with self.assertRaises(CommandError): call_command("retry_outbox_event", str(item.pk))
        call_command("retry_outbox_event", str(item.pk), confirm=True)
        item.refresh_from_db()
        self.assertEqual(item.attempts, 0)
        self.assertIsNotNone(item.next_attempt_at)
        self.assertEqual(item.last_error_code, "MANUAL_RETRY")
