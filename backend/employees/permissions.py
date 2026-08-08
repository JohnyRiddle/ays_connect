from rest_framework.permissions import BasePermission

MANAGER_ROLES = {"manager", "facility_manager", "hr", "admin", "executive", "owner", "auditor"}
class IsOrganizationManager(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated: return False
        if request.user.is_superuser: return True
        return request.user.role_assignments.filter(role__code__in=MANAGER_ROLES).exists()
