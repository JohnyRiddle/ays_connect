from rest_framework.permissions import BasePermission

LEARNING_MANAGER_ROLES = {"manager", "facility_manager", "hr", "admin", "executive", "owner"}


def is_learning_manager(user):
    return user.is_superuser or user.role_assignments.filter(role__code__in=LEARNING_MANAGER_ROLES).exists()


class IsLearningManager(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and is_learning_manager(request.user))
