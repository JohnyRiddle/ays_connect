from rest_framework import viewsets
from .models import Permission, Role, RolePermission
from .permissions import InternalAPIPermission
from .serializers import PermissionSerializer, RolePermissionSerializer, RoleSerializer


class PermissionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Permission.objects.all().order_by("code")
    serializer_class = PermissionSerializer
    permission_classes = (InternalAPIPermission,)
    permission_domain = "role"


class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.prefetch_related("permission_grants__permission").order_by("name")
    serializer_class = RoleSerializer
    permission_classes = (InternalAPIPermission,)
    permission_domain = "role"


class RolePermissionViewSet(viewsets.ModelViewSet):
    queryset = RolePermission.objects.select_related("role", "permission")
    serializer_class = RolePermissionSerializer
    permission_classes = (InternalAPIPermission,)
    permission_domain = "role"
