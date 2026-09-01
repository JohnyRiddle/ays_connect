from django.db import transaction
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder
import json

from .models import OutboxEvent
from django.db.models import Q
from datetime import timedelta


MAX_OUTBOX_ATTEMPTS = 5


class DomainEventService:
    @staticmethod
    def publish(*, event_type, entity, payload, actor=None, correlation_id=None, causation_id=None):
        return OutboxEvent.objects.create(
            event_type=event_type,
            entity_type=entity.__class__.__name__,
            entity_id=str(entity.pk),
            actor_id=str(actor.pk) if actor else "",
            occurred_at=timezone.now(),
            payload=json.loads(json.dumps(payload or {}, cls=DjangoJSONEncoder)),
            correlation_id=correlation_id,
            causation_id=causation_id,
        )


class OutboxProcessor:
    @staticmethod
    @transaction.atomic
    def process_batch(handler, limit=100):
        now = timezone.now()
        events = list(OutboxEvent.objects.select_for_update(skip_locked=True).filter(
            Q(status=OutboxEvent.Status.PENDING) | Q(status=OutboxEvent.Status.FAILED, attempts__lt=MAX_OUTBOX_ATTEMPTS, next_attempt_at__lte=now)
        ).order_by("created_at")[:limit])
        for event in events:
            event.attempts += 1
            try:
                handler(event)
                event.status = OutboxEvent.Status.PROCESSED
                event.processed_at = timezone.now()
                event.last_error = ""
                event.last_error_code = ""; event.next_attempt_at = None; event.failed_at = None
            except Exception as exc:
                event.status = OutboxEvent.Status.FAILED
                event.last_error_code = exc.__class__.__name__[:120]
                event.last_error = "Handler failed; inspect sanitized worker logs."
                event.failed_at = now
                event.next_attempt_at = None if event.attempts >= MAX_OUTBOX_ATTEMPTS else now + timedelta(seconds=min(3600, 60 * (2 ** event.attempts)))
            event.save(update_fields=["attempts", "status", "processed_at", "last_error", "last_error_code", "next_attempt_at", "failed_at"])
        return len(events)
