from django.db.models import Q

from .models import KnowledgeMaterial, MaterialAccessRule

MANAGE_ROLES = {"manager", "facility_manager", "hr", "admin", "executive", "owner"}
LEVEL_RANK = {"VIEW": 1, "DOWNLOAD": 2, "EDIT": 3, "MANAGE": 4}


def is_manager(user):
    return user.is_superuser or user.role_assignments.filter(role__code__in=MANAGE_ROLES).exists()


def employee_for(user):
    return getattr(user, "employee", None)


def accessible_materials(user, minimum_level="VIEW"):
    qs = KnowledgeMaterial.objects.all()
    if user.is_superuser:
        return qs
    employee = employee_for(user)
    role_ids = list(user.role_assignments.values_list("role_id", flat=True))
    matched = Q(access_rules__role_id__in=role_ids)
    if employee:
        facility_ids = list(employee.facilities.values_list("id", flat=True))
        region_ids = list(employee.facilities.values_list("cluster__region_id", flat=True))
        matched |= Q(access_rules__employee=employee)
        matched |= Q(access_rules__position__iexact=employee.position)
        matched |= Q(access_rules__department=employee.department)
        matched |= Q(access_rules__facility_id__in=facility_ids)
        matched |= Q(access_rules__region_id__in=region_ids)
    allowed_levels = [level for level, rank in LEVEL_RANK.items() if rank >= LEVEL_RANK[minimum_level]]
    open_material = Q(access_rules__isnull=True)
    matching_rule = matched & Q(access_rules__access_level__in=allowed_levels)
    own = Q(owner=user)
    return qs.filter(open_material | matching_rule | own).distinct()


def can_manage(user, material=None):
    return is_manager(user) or bool(material and material.owner_id == user.id)


def can_download(user, material):
    if not material.is_downloadable:
        return can_manage(user, material)
    return accessible_materials(user, MaterialAccessRule.Level.DOWNLOAD).filter(pk=material.pk).exists() or not material.access_rules.exists()
