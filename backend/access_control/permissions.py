from rest_framework.permissions import BasePermission
from .services import PermissionService


class InternalAPIPermission(BasePermission):
    permission_map = {"GET": "view", "HEAD": "view", "OPTIONS": "view", "POST": "manage", "PUT": "manage", "PATCH": "manage", "DELETE": "manage"}

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        employee = getattr(request.user, "employee", None)
        domain = getattr(view, "permission_domain", None)
        action = self.permission_map.get(request.method, "manage")
        return bool(domain and PermissionService.has_permission(employee=employee, permission=f"{domain}.{action}"))

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True
        employee = getattr(request.user, "employee", None)
        domain = getattr(view, "permission_domain", None)
        action = self.permission_map.get(request.method, "manage")
        return PermissionService.has_permission(employee=employee, permission=f"{domain}.{action}", obj=obj)
