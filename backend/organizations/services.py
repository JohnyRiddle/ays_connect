from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction

from audit.services import AuditService
from events.services import DomainEventService
from .models import OrgUnit


class OrgUnitCycleError(ValidationError):
    pass


class OrgUnitService:
    @staticmethod
    def _validate_parent(unit: OrgUnit | None, parent: OrgUnit | None) -> None:
        if parent is None:
            return
        if unit and parent.pk == unit.pk:
            raise OrgUnitCycleError("Подразделение не может быть родителем самого себя.")
        cursor = parent
        visited = set()
        while cursor:
            if cursor.pk in visited or (unit and cursor.pk == unit.pk):
                raise OrgUnitCycleError("Нельзя создать циклическую иерархию подразделений.")
            visited.add(cursor.pk)
            cursor = cursor.parent

    @classmethod
    @transaction.atomic
    def create(cls, *, actor_user=None, **data) -> OrgUnit:
        cls._validate_parent(None, data.get("parent"))
        unit = OrgUnit.objects.create(**data)
        AuditService.record(actor_user=actor_user, action="org_unit.created", entity=unit, new_value={"name": unit.name})
        DomainEventService.publish(event_type="org_unit.created", entity=unit, actor=actor_user, payload={"name": unit.name})
        return unit

    @classmethod
    @transaction.atomic
    def move(cls, *, unit: OrgUnit, parent: OrgUnit | None, actor_user=None) -> OrgUnit:
        locked = OrgUnit.objects.select_for_update().get(pk=unit.pk)
        cls._validate_parent(locked, parent)
        old_parent = str(locked.parent_id) if locked.parent_id else None
        locked.parent = parent
        locked.save(update_fields=["parent", "updated_at"])
        AuditService.record(actor_user=actor_user, action="org_unit.moved", entity=locked, old_value={"parent_id": old_parent}, new_value={"parent_id": str(parent.pk) if parent else None})
        DomainEventService.publish(event_type="org_unit.moved", entity=locked, actor=actor_user, payload={"parent_id": str(parent.pk) if parent else None})
        return locked
