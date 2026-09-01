from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from performance.models import PerformanceRecalculation
from performance.models import PerformanceEventReceipt
from events.models import OutboxEvent


class PerformanceRecoveryTests(TestCase):
    def test_enqueue_accepts_canonical_domain_event_entity_types(self):
        event = OutboxEvent.objects.create(
            event_type="task.created",
            entity_type="Task",
            entity_id="00000000-0000-0000-0000-000000000001",
            occurred_at=timezone.now(),
        )

        call_command("enqueue_performance", batch_size=10, stdout=StringIO())

        self.assertTrue(PerformanceEventReceipt.objects.filter(event_id=event.event_id).exists())
        self.assertEqual(PerformanceRecalculation.objects.count(), 1)

    def test_abandoned_claim_is_recovered(self):
        item=PerformanceRecalculation.objects.create(deduplication_key="abandoned",period_from=timezone.now()-timedelta(days=2),period_to=timezone.now()-timedelta(days=1),reporting_timezone="UTC",status="processing",locked_at=timezone.now()-timedelta(hours=1))
        output=StringIO();call_command("process_performance",batch_size=1,stdout=output);item.refresh_from_db()
        self.assertEqual(item.status,"completed");self.assertIn("recovered=1",output.getvalue())
