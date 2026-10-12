"""No implicit legacy privileges for Location-enrolled accounts.

Legacy Facility/Zone has no approved mapping to Location scope. Preserve existing
accounts, but do not let a new read-only role inherit IsAuthenticated-only writes.
"""
LEGACY_PREFIXES = tuple("/api/v1/" + name + "/" for name in (
    "tasks", "checklists", "sensors", "incidents", "analytics", "knowledge", "learning", "organization", "iiko"))


def legacy_access_allowed(user):
    if user.is_superuser:
        return True
    from employees.models import RegistrationRequest
    return not RegistrationRequest.objects.filter(matched_employee__user_id=user.pk,
        employment_location__isnull=False, status="approved").exists()
