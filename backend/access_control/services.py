from django.core.exceptions import PermissionDenied
from django.db import models, transaction
from django.utils import timezone

from audit.services import AuditService
from events.services import DomainEventService
from .models import EmployeeRole
from .policies import EmployeeAccessPolicy, OrganizationAccessPolicy


class PermissionService:
    @staticmethod
    def has_permission(*, employee, permission: str, obj=None) -> bool:
        if employee is None or not employee.is_active:
            return False
        if obj is not None and obj.__class__.__module__.startswith("work_tasks"):
            from work_tasks.policies import TaskAccessPolicy
            return TaskAccessPolicy.allows(employee=employee, permission=permission, task=obj)
        now = timezone.now()
        grants = EmployeeRole.objects.filter(
            employee=employee, is_active=True, role__is_active=True,
            role__permission_grants__permission__code=permission,
        ).filter(
            models.Q(active_from__isnull=True) | models.Q(active_from__lte=now),
            models.Q(active_until__isnull=True) | models.Q(active_until__gte=now),
        ).select_related("org_unit", "legal_entity", "location", "role").prefetch_related("role__permission_grants")
        for assignment in grants.distinct():
            scopes = assignment.role.permission_grants.filter(permission__code=permission).values_list("scope", flat=True)
            for scope in scopes:
                if obj is None:
                    if scope == "global" or assignment.org_unit_id or assignment.legal_entity_id or assignment.location_id:
                        return True
                    continue
                policy = EmployeeAccessPolicy if obj.__class__.__name__ == "Employee" else OrganizationAccessPolicy
                if policy.allows(actor=employee, target=obj, grant=assignment, scope=scope):
                    return True
        return False

    @classmethod
    def require_permission(cls, **kwargs):
        if not cls.has_permission(**kwargs):
            raise PermissionDenied("Недостаточно прав для выполнения операции.")


class RoleService:
    @staticmethod
    @transaction.atomic
    def assign_role(*, employee, role, actor_user=None, **context):
        assignment = EmployeeRole.objects.create(employee=employee, role=role, **context)
        AuditService.record(actor_user=actor_user, action="role.assigned", entity=assignment, new_value={"employee_id": str(employee.pk), "role": role.code})
        DomainEventService.publish(event_type="role.assigned", entity=assignment, actor=actor_user, payload={"employee_id": str(employee.pk), "role": role.code})
        return assignment

    @staticmethod
    @transaction.atomic
    def revoke_role(*, assignment, actor_user=None):
        assignment = EmployeeRole.objects.select_for_update().get(pk=assignment.pk)
        assignment.is_active = False
        assignment.save(update_fields=["is_active"])
        AuditService.record(actor_user=actor_user, action="role.revoked", entity=assignment, old_value={"is_active": True}, new_value={"is_active": False})
        DomainEventService.publish(event_type="role.revoked", entity=assignment, actor=actor_user, payload={})
        return assignment
