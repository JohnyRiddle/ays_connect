from django.db.models import Q
from django.utils import timezone

from access_control.models import EmployeeRole, Scope


class TaskAccessPolicy:
    @staticmethod
    def _grants(employee, permission):
        now = timezone.now()
        return EmployeeRole.objects.filter(
            employee=employee, is_active=True, role__is_active=True,
            role__permission_grants__permission__code=permission,
        ).filter(
            Q(active_from__isnull=True) | Q(active_from__lte=now),
            Q(active_until__isnull=True) | Q(active_until__gte=now),
        ).select_related("org_unit", "legal_entity", "location", "role").distinct()

    @classmethod
    def allows(cls, *, employee, permission, task=None):
        if not employee or not employee.is_active:
            return False
        for grant in cls._grants(employee, permission):
            scopes = grant.role.permission_grants.filter(permission__code=permission).values_list("scope", flat=True)
            for scope in scopes:
                if task is None:
                    return True
                if scope == Scope.GLOBAL:
                    return True
                participating = employee.pk in {task.author_id, task.responsible_employee_id, task.executor_employee_id} or task.watcher_records.filter(employee=employee, removed_at__isnull=True).exists()
                if scope == Scope.PARTICIPATING and participating:
                    return True
                if scope == Scope.OWN and employee.pk in {task.responsible_employee_id, task.executor_employee_id}:
                    return True
                if scope == Scope.ORG_UNIT and task.org_unit_id == (grant.org_unit_id or employee.org_unit_id):
                    return True
                if scope == Scope.LEGAL_ENTITY and task.legal_entity_id == (grant.legal_entity_id or employee.legal_entity_id):
                    return True
                if scope == Scope.TEAM and task.executor_employee and task.executor_employee.manager_id == employee.pk:
                    return True
        return False

    @classmethod
    def visibility_query(cls, *, employee, permission="task.view"):
        query = Q(pk__in=[])
        for grant in cls._grants(employee, permission):
            for scope in grant.role.permission_grants.filter(permission__code=permission).values_list("scope", flat=True):
                if scope == Scope.GLOBAL:
                    return Q()
                if scope == Scope.PARTICIPATING:
                    query |= Q(author=employee) | Q(responsible_employee=employee) | Q(executor_employee=employee) | Q(watcher_records__employee=employee, watcher_records__removed_at__isnull=True)
                elif scope == Scope.OWN:
                    query |= Q(responsible_employee=employee) | Q(executor_employee=employee)
                elif scope == Scope.ORG_UNIT:
                    query |= Q(org_unit_id=grant.org_unit_id or employee.org_unit_id)
                elif scope == Scope.LEGAL_ENTITY:
                    query |= Q(legal_entity_id=grant.legal_entity_id or employee.legal_entity_id)
                elif scope == Scope.TEAM:
                    query |= Q(executor_employee__manager=employee)
        return query
