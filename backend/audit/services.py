from .models import AuditEvent
import json
from django.core.serializers.json import DjangoJSONEncoder


def _json_safe(value):
    return json.loads(json.dumps(value or {}, cls=DjangoJSONEncoder))


class AuditService:
    @staticmethod
    def record(*, action, entity, actor_user=None, actor_employee=None, old_value=None, new_value=None, metadata=None, request=None, correlation_id=None):
        return AuditEvent.objects.create(
            actor=actor_user,
            actor_employee=actor_employee,
            action=action,
            entity_type=entity.__class__.__name__,
            entity_id=str(entity.pk),
            old_values=_json_safe(old_value),
            new_values=_json_safe(new_value),
            metadata=_json_safe(metadata),
            ip_address=request.META.get("REMOTE_ADDR") if request else None,
            user_agent=request.META.get("HTTP_USER_AGENT", "") if request else "",
            correlation_id=correlation_id,
        )


def record(actor, action, entity, old_values=None, new_values=None, request=None):
    return AuditService.record(actor_user=actor, action=action, entity=entity, old_value=old_values, new_value=new_values, request=request)
