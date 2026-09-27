from django.db.models import Q
from django.utils import timezone

from access_control.models import EmployeeRole, Scope

from .models import Project


class ProjectAccessPolicy:
    @staticmethod
    def _grants(employee, permission):
        now = timezone.now()
        return EmployeeRole.objects.filter(employee=employee, is_active=True, role__is_active=True,
            role__permission_grants__permission__code=permission).filter(
            Q(active_from__isnull=True) | Q(active_from__lte=now),
            Q(active_until__isnull=True) | Q(active_until__gte=now),
        ).distinct()

    @classmethod
    def visibility_query(cls, employee, permission="project.view"):
        if not employee or not employee.is_active:
            return Q(pk__in=[])
        query = Q(pk__in=[])
        for grant in cls._grants(employee, permission):
            for scope in grant.role.permission_grants.filter(permission__code=permission).values_list("scope", flat=True):
                if scope == Scope.GLOBAL:
                    return Q()
                if scope == Scope.PARTICIPATING:
                    query |= Q(manager=employee) | Q(members__employee=employee, members__left_at__isnull=True)
                elif scope == Scope.OWN:
                    query |= Q(manager=employee)
                elif scope == Scope.ORG_UNIT:
                    context = grant.org_unit_id or employee.org_unit_id
                    if context: query |= Q(org_unit_id=context)
                elif scope == Scope.LEGAL_ENTITY:
                    context = grant.legal_entity_id or employee.legal_entity_id
                    if context: query |= Q(org_unit__legal_entity_id=context) | Q(location__legal_entity_id=context)
                elif scope == Scope.TEAM:
                    query |= Q(members__employee__manager=employee, members__left_at__isnull=True)
        return query

    @classmethod
    def visible_to(cls, employee, permission="project.view"):
        return Project.objects.filter(cls.visibility_query(employee, permission)).distinct()

    @classmethod
    def allows(cls, employee, permission, project=None):
        if not employee or not employee.is_active:
            return False
        if project is None:
            return cls._grants(employee, permission).exists()
        return cls.visible_to(employee, permission).filter(pk=project.pk).exists()
