from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from audit.services import AuditService
from events.services import DomainEventService
from .models import Employee, FunctionalGroup, FunctionalGroupMembership


class EmployeeService:
    @staticmethod
    @transaction.atomic
    def create(*, actor_user=None, **data) -> Employee:
        employee = Employee.objects.create(**data)
        AuditService.record(actor_user=actor_user, action="employee.created", entity=employee, new_value={"display_name": employee.display_name})
        DomainEventService.publish(event_type="employee.created", entity=employee, actor=actor_user, payload={"display_name": employee.display_name})
        return employee

    @staticmethod
    @transaction.atomic
    def deactivate(*, employee: Employee, actor_user=None) -> Employee:
        locked = Employee.objects.select_for_update().get(pk=employee.pk)
        old = {"is_active": locked.is_active, "status": locked.status}
        locked.is_active = False
        locked.status = Employee.Status.DISMISSED
        locked.dismissed_at = locked.dismissed_at or timezone.localdate()
        locked.updated_at = timezone.now()
        locked.save(update_fields=["is_active", "status", "dismissed_at", "updated_at"])
        AuditService.record(actor_user=actor_user, action="employee.deactivated", entity=locked, old_value=old, new_value={"is_active": False, "status": locked.status})
        DomainEventService.publish(event_type="employee.deactivated", entity=locked, actor=actor_user, payload={})
        return locked


class FunctionalGroupService:
    @staticmethod
    @transaction.atomic
    def add_member(*, group: FunctionalGroup, employee: Employee, actor_user=None, **data) -> FunctionalGroupMembership:
        membership = FunctionalGroupMembership.objects.select_for_update().filter(group=group, employee=employee, is_active=True).first()
        if membership is None:
            membership = FunctionalGroupMembership.objects.create(group=group, employee=employee, is_active=True, **data)
        else:
            for field, value in data.items():
                setattr(membership, field, value)
            if data:
                membership.save(update_fields=list(data))
        AuditService.record(actor_user=actor_user, action="functional_group.member_added", entity=group, new_value={"employee_id": str(employee.pk)})
        DomainEventService.publish(event_type="functional_group.member_added", entity=group, actor=actor_user, payload={"employee_id": str(employee.pk)})
        return membership

    @staticmethod
    @transaction.atomic
    def remove_member(*, group: FunctionalGroup, employee: Employee, actor_user=None) -> None:
        membership = FunctionalGroupMembership.objects.select_for_update().get(group=group, employee=employee, is_active=True)
        membership.is_active = False
        membership.active_until = membership.active_until or timezone.now()
        membership.save(update_fields=["is_active", "active_until"])
        AuditService.record(actor_user=actor_user, action="functional_group.member_removed", entity=group, old_value={"employee_id": str(employee.pk)})
        DomainEventService.publish(event_type="functional_group.member_removed", entity=group, actor=actor_user, payload={"employee_id": str(employee.pk)})
