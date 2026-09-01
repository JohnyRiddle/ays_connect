from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from events.models import OutboxEvent
from events.services import MAX_OUTBOX_ATTEMPTS


class Command(BaseCommand):
    help = "Explicitly requeue one terminal Outbox event after its handler has been repaired."

    def add_arguments(self, parser):
        parser.add_argument("event_id")
        parser.add_argument("--confirm", action="store_true")

    def handle(self, *args, **options):
        if not options["confirm"]:
            raise CommandError("Refusing to retry without --confirm.")
        try:
            event = OutboxEvent.objects.get(pk=options["event_id"])
        except (OutboxEvent.DoesNotExist, ValueError):
            raise CommandError("Outbox event not found.")
        if event.status != OutboxEvent.Status.FAILED or event.attempts < MAX_OUTBOX_ATTEMPTS:
            raise CommandError("Only terminal failed events can be retried manually.")
        event.attempts = 0
        event.next_attempt_at = timezone.now()
        event.last_error_code = "MANUAL_RETRY"
        event.last_error = "Terminal event explicitly requeued by operator."
        event.save(update_fields=("attempts", "next_attempt_at", "last_error_code", "last_error"))
        self.stdout.write(self.style.SUCCESS(f"requeued={event.pk}"))
