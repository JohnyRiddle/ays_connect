from django.db.models import Q
from django.utils import timezone

from access_control.models import EmployeeRole, Scope
from employees.models import Employee


PERMISSION_CODES = ("performance.view", "performance.view_management")


def visible_employees(user):
    if user.is_superuser:
        return Employee.objects.all()
    actor = getattr(user, "employee", None)
    if not actor:
        return Employee.objects.none()
    now = timezone.now()
    grants = EmployeeRole.objects.filter(
        employee=actor, is_active=True, role__is_active=True,
        role__permission_grants__permission__code__in=PERMISSION_CODES,
    ).filter(Q(active_from__isnull=True) | Q(active_from__lte=now)).filter(Q(active_until__isnull=True) | Q(active_until__gt=now)).select_related("org_unit", "legal_entity", "location").prefetch_related("role__permission_grants")
    query = Q(pk=actor.pk) | Q(manager=actor)
    for assignment in grants:
        for grant in assignment.role.permission_grants.all():
            if grant.permission.code not in PERMISSION_CODES: continue
            if grant.scope == Scope.GLOBAL: return Employee.objects.all()
            if grant.scope == Scope.TEAM: query |= Q(manager=actor)
            elif grant.scope == Scope.ORG_UNIT: query |= Q(org_unit=assignment.org_unit or actor.org_unit)
            elif grant.scope == Scope.LEGAL_ENTITY: query |= Q(legal_entity=assignment.legal_entity or actor.legal_entity)
    return Employee.objects.filter(query).distinct()
