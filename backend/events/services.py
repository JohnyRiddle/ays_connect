from django.db import transaction
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder
import json

from .models import OutboxEvent


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
        events = list(OutboxEvent.objects.select_for_update(skip_locked=True).filter(status=OutboxEvent.Status.PENDING).order_by("created_at")[:limit])
        for event in events:
            event.attempts += 1
            try:
                handler(event)
                event.status = OutboxEvent.Status.PROCESSED
                event.processed_at = timezone.now()
                event.last_error = ""
            except Exception as exc:
                event.status = OutboxEvent.Status.FAILED
                event.last_error = str(exc)[:2000]
            event.save(update_fields=["attempts", "status", "processed_at", "last_error"])
        return len(events)
