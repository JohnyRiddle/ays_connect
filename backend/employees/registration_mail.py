"""Tombstone consumer: registration must never send or accumulate mail."""
from django.utils import timezone
from events.models import OutboxEvent

EVENTS = ("registration.mail.requested", "registration.invite_mail.requested")


def process_mail(batch_size=100, provider=None):
    # Retire old jobs even if SMTP is enabled; never invoke a provider.
    OutboxEvent.objects.filter(event_type__in=EVENTS).exclude(status="processed").update(
        status="failed", last_error_code="REGISTRATION_MAIL_DISABLED", next_attempt_at=None,
        failed_at=timezone.now())
    return 0
