from datetime import timedelta
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.utils import timezone

from events.models import OutboxEvent
from performance.models import PerformanceEventReceipt, PerformanceRecalculation


class Command(BaseCommand):
    help = "Translate relevant Outbox events into idempotent performance recalculation work."

    def add_arguments(self, parser): parser.add_argument("--batch-size", type=int, default=500)

    def handle(self, *args, **options):
        zone = ZoneInfo("Asia/Novosibirsk"); created = 0
        events = OutboxEvent.objects.filter(entity_type__in=("task", "service_request", "sla_instance")).exclude(event_id__in=PerformanceEventReceipt.objects.values("event_id")).order_by("created_at")[:options["batch_size"]]
        for event in events:
            local = event.occurred_at.astimezone(zone); start = local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
            job, was_created = PerformanceRecalculation.objects.get_or_create(
                deduplication_key=f"period:{zone.key}:{start.isoformat()}:{next_month.isoformat()}",
                defaults={"period_from": start, "period_to": next_month, "reporting_timezone": zone.key},
            )
            if not was_created and job.status == PerformanceRecalculation.Status.COMPLETED:
                job.status = PerformanceRecalculation.Status.PENDING
                job.last_error = ""
                job.save(update_fields=("status", "last_error", "updated_at"))
            PerformanceEventReceipt.objects.get_or_create(event_id=event.event_id, defaults={"recalculation": job})
            created += int(was_created)
        self.stdout.write(f"enqueued={created}")
