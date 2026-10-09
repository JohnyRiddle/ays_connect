from django.db.models import Q
from django.utils import timezone

from access_control.models import EmployeeRole
from .models import Location


OPERATIONS = ("create", "edit", "manage_zones", "assign_responsible", "change_status", "archive", "restore", "move")


class LocationAccessPolicy:
    """Object-specific scopes; geography grants intentionally fail closed."""
    @staticmethod
    def grants(user, permission):
        if not user.is_authenticated or not user.is_active:
            return EmployeeRole.objects.none()
        actor = getattr(user, "employee", None)
        if not actor or not actor.is_active:
            return EmployeeRole.objects.none()
        now = timezone.now()
        # Existing manage means the explicit mutation allowlist, never view.
        codes = [permission]
        if permission in {f"location.{op}" for op in OPERATIONS}:
            codes.append("location.manage")
        return EmployeeRole.objects.filter(employee=actor, is_active=True, role__is_active=True,
            role__permission_grants__permission__code__in=codes).filter(
            Q(active_from__isnull=True) | Q(active_from__lte=now),
            Q(active_until__isnull=True) | Q(active_until__gt=now),
        ).select_related("location").prefetch_related("role__permission_grants__permission").distinct()

    @staticmethod
    def descendants(root):
        # Works for arbitrarily nested zones without relying on names or classification.
        result, frontier = {root.pk}, {root.pk}
        while frontier:
            found = set(Location.objects.filter(parent_id__in=frontier, node_kind=Location.NodeKind.ZONE).values_list("pk", flat=True)) - result
            result.update(found)
            frontier = found
        return result

    @classmethod
    def query(cls, user, permission="location.view"):
        if user.is_authenticated and user.is_active and user.is_superuser:
            return Q()
        query = Q(pk__in=[])
        for grant in cls.grants(user, permission):
            for item in grant.role.permission_grants.all():
                if item.permission.code != permission and not (item.permission.code == "location.manage" and permission in {f"location.{op}" for op in OPERATIONS}):
                    continue
                if item.scope == "global":
                    return Q()
                if item.scope == "legal_entity" and grant.legal_entity_id:
                    query |= Q(legal_entity_id=grant.legal_entity_id)
                if item.scope == "location" and grant.location_id and grant.location.node_kind == Location.NodeKind.OBJECT:
                    query |= Q(pk__in=cls.descendants(grant.location))
        return query

    @classmethod
    def visible(cls, user, permission="location.view"):
        return Location.objects.filter(cls.query(user, permission)).distinct()

    @classmethod
    def allows(cls, user, permission, location):
        return cls.visible(user, permission).filter(pk=location.pk).exists()

    @classmethod
    def create_context(cls, user, candidate, permission="location.create"):
        if user.is_authenticated and user.is_active and user.is_superuser:
            return True
        for grant in cls.grants(user, permission):
            for item in grant.role.permission_grants.all():
                codes = {permission}
                if permission in {f"location.{op}" for op in OPERATIONS}:
                    codes.add("location.manage")
                if item.permission.code not in codes:
                    continue
                if item.scope == "global":
                    return True
                if item.scope == "legal_entity" and grant.legal_entity_id and candidate.legal_entity_id == grant.legal_entity_id:
                    return True
        # location scope permits zones, not creation of a sibling object.
        return False
