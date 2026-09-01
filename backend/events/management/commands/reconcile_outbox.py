from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from events.models import OutboxEvent
from events.services import MAX_OUTBOX_ATTEMPTS


class Command(BaseCommand):
    help = "Recover retryable failed/abandoned Outbox events without touching terminal poison events."

    def add_arguments(self, parser):
        parser.add_argument("--stale-minutes", type=int, default=10)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        now=timezone.now(); stale=now-timedelta(minutes=max(1,options["stale_minutes"]))
        processing=OutboxEvent.objects.filter(status=OutboxEvent.Status.PROCESSING, created_at__lt=stale, attempts__lt=MAX_OUTBOX_ATTEMPTS)
        retryable=OutboxEvent.objects.filter(status=OutboxEvent.Status.FAILED, attempts__lt=MAX_OUTBOX_ATTEMPTS, next_attempt_at__isnull=True)
        count=processing.count()+retryable.count()
        if not options["dry_run"]:
            processing.update(status=OutboxEvent.Status.FAILED,last_error_code="ABANDONED_CLAIM",last_error="Abandoned claim recovered.",failed_at=now,next_attempt_at=now)
            retryable.update(next_attempt_at=now)
        self.stdout.write(f"recoverable={count} dry_run={options['dry_run']}")
