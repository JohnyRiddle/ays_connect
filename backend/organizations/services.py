from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

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
        if parent.status != OrgUnit.Status.ACTIVE or not parent.is_active:
            raise ValidationError("Закрытое подразделение нельзя назначить родителем.")
        if unit:
            if unit.legal_entity_id and parent.legal_entity_id and unit.legal_entity_id != parent.legal_entity_id:
                raise ValidationError("Родитель и подразделение должны относиться к одному юридическому лицу.")
            if parent.valid_from > unit.valid_from or (parent.valid_to and (not unit.valid_to or unit.valid_to > parent.valid_to)):
                raise ValidationError("Период подразделения должен находиться внутри периода родителя.")

    @classmethod
    @transaction.atomic
    def create(cls, *, actor_user=None, **data) -> OrgUnit:
        cls._validate_parent(OrgUnit(**data), data.get("parent"))
        unit = OrgUnit.objects.create(**data)
        AuditService.record(actor_user=actor_user, action="people.org_unit.created", entity=unit, new_value={"name": unit.name})
        DomainEventService.publish(event_type="people.org_unit.created", entity=unit, actor=actor_user, payload={"name": unit.name})
        return unit

    @classmethod
    @transaction.atomic
    def move(cls, *, unit: OrgUnit, parent: OrgUnit | None, expected_version: int | None = None, actor_user=None) -> OrgUnit:
        list(OrgUnit.objects.select_for_update().values_list("pk", flat=True))
        locked = OrgUnit.objects.get(pk=unit.pk)
        if expected_version is not None and locked.version != expected_version:
            raise ValidationError("Версия подразделения устарела.")
        if locked.status != OrgUnit.Status.ACTIVE:
            raise ValidationError("Закрытое подразделение нельзя перемещать.")
        cls._validate_parent(locked, parent)
        old_parent = str(locked.parent_id) if locked.parent_id else None
        locked.parent = parent; locked.version += 1
        locked.save(update_fields=["parent", "version", "updated_at"])
        AuditService.record(actor_user=actor_user, action="people.org_unit.moved", entity=locked, old_value={"parent_id": old_parent}, new_value={"parent_id": str(parent.pk) if parent else None})
        DomainEventService.publish(event_type="people.org_unit.moved", entity=locked, actor=actor_user, payload={"parent_id": str(parent.pk) if parent else None})
        return locked

    @classmethod
    @transaction.atomic
    def close(cls, *, unit, expected_version: int | None = None, actor_user=None, reason=""):
        locked=OrgUnit.objects.select_for_update().get(pk=unit.pk)
        if locked.status==OrgUnit.Status.CLOSED: return locked
        if expected_version is not None and locked.version != expected_version:
            raise ValidationError("Версия подразделения устарела.")
        from employees.models import EmployeeAssignment
        if EmployeeAssignment.objects.filter(org_unit=locked,status=EmployeeAssignment.Status.ACTIVE).exists():
            raise ValidationError("Нельзя закрыть подразделение с активными назначениями.")
        if OrgUnit.objects.filter(parent=locked,status=OrgUnit.Status.ACTIVE,is_active=True).exists():
            raise ValidationError("Нельзя закрыть подразделение с активными дочерними подразделениями.")
        locked.status=OrgUnit.Status.CLOSED; locked.valid_to=max(timezone.now(),locked.valid_from); locked.is_active=False; locked.version+=1
        locked.save(update_fields=["status","valid_to","is_active","version","updated_at"])
        AuditService.record(actor_user=actor_user,action="people.org_unit.closed",entity=locked,new_value={"reason":reason})
        DomainEventService.publish(event_type="people.org_unit.closed",entity=locked,actor=actor_user,payload={"reason":reason})
        return locked
