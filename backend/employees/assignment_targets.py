"""Work assignment choices share a scoped, active employee boundary."""
from django.db.models import Q
from django.utils import timezone
from rest_framework.permissions import BasePermission
from access_control.models import EmployeeRole
from .models import Employee

BLOCKED = {"archived", "suspended", "dismissed", "terminated", "inactive", "onboarding", "pending", "rejected", "email_pending"}


def assignable_employees():
    return Employee.objects.filter(is_active=True).exclude(status__in=BLOCKED).filter(
        Q(user__isnull=True) | Q(user__is_active=True))


def assignment_visibility(user):
    qs = assignable_employees()
    if not user.is_authenticated or not user.is_active:
        return qs.none(), False, False
    actor = getattr(user, "employee", None)
    if actor and not qs.filter(pk=actor.pk).exists():
        return qs.none(), False, False
    if user.is_superuser:
        return qs, True, True
    if not actor:
        return qs.none(), False, False
    now = timezone.now()
    grants = EmployeeRole.objects.filter(employee=actor, is_active=True, role__is_active=True,
        role__permission_grants__permission__code="employee.view").filter(
        Q(active_from__isnull=True) | Q(active_from__lte=now),
        Q(active_until__isnull=True) | Q(active_until__gt=now)).select_related("role")
    predicate = Q(pk__in=[])
    allowed = False
    for grant in grants.distinct():
        for scope in grant.role.permission_grants.filter(permission__code="employee.view").values_list("scope", flat=True):
            if scope == "global":
                return qs, True, True
            if scope == "own":
                predicate |= Q(pk=actor.pk); allowed = True
            elif scope == "location" and grant.location_id:
                predicate |= Q(primary_location_id=grant.location_id); allowed = True
            elif scope == "org_unit":
                context = grant.org_unit_id or actor.org_unit_id
                if context:
                    predicate |= Q(org_unit_id=context); allowed = True
            elif scope == "legal_entity":
                context = grant.legal_entity_id or actor.legal_entity_id
                if context:
                    predicate |= Q(legal_entity_id=context); allowed = True
            elif scope == "team":
                predicate |= Q(manager_id=actor.pk); allowed = True
                if actor.manager_id:
                    predicate |= Q(manager_id=actor.manager_id)
    return qs.filter(predicate).distinct(), False, allowed


class AssignmentLookupPermission(BasePermission):
    def has_permission(self, request, view):
        return assignment_visibility(request.user)[2]

    def has_object_permission(self, request, view, obj):
        # Retrieval is restricted by the same queryset as list/count/search.
        return view.get_queryset().filter(pk=obj.pk).exists()
