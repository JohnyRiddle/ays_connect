from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import timedelta

from performance.models import PerformanceRecalculation
from operations.heartbeat import record_worker_cycle


class Command(BaseCommand):
    help = "Claim recalculation jobs concurrently using PostgreSQL SKIP LOCKED."

    def add_arguments(self, parser): parser.add_argument("--batch-size", type=int, default=10)

    def handle(self, *args, **options):
        processed = 0
        recovered = PerformanceRecalculation.objects.filter(status=PerformanceRecalculation.Status.PROCESSING, locked_at__lt=timezone.now()-timedelta(minutes=15)).update(status=PerformanceRecalculation.Status.PENDING, locked_at=None, last_error="Recovered abandoned claim.")
        while processed < options["batch_size"]:
            with transaction.atomic():
                job = PerformanceRecalculation.objects.select_for_update(skip_locked=True).filter(status__in=(PerformanceRecalculation.Status.PENDING, PerformanceRecalculation.Status.FAILED), attempts__lt=5).order_by("created_at").first()
                if not job: break
                job.status = PerformanceRecalculation.Status.PROCESSING; job.attempts += 1; job.locked_at = timezone.now(); job.save(update_fields=("status", "attempts", "locked_at", "updated_at"))
            try:
                call_command("rebuild_performance", **{"period_from": job.period_from.isoformat(), "period_to": job.period_to.isoformat(), "timezone": job.reporting_timezone})
            except Exception as exc:
                job.status = PerformanceRecalculation.Status.FAILED; job.last_error = str(exc)[:4000]
            else:
                job.status = PerformanceRecalculation.Status.COMPLETED; job.last_error = ""; processed += 1
            job.locked_at = None; job.save(update_fields=("status", "last_error", "locked_at", "updated_at"))
        record_worker_cycle("performance",processed=processed,metadata={"recovered":recovered})
        self.stdout.write(f"processed={processed} recovered={recovered}")
