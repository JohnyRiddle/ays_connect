from rest_framework import serializers
from .models import EmployeeRole, Permission, Role, RolePermission


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = "__all__"
        read_only_fields = ("id",)


class RolePermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RolePermission
        fields = "__all__"
        read_only_fields = ("id",)


class RoleSerializer(serializers.ModelSerializer):
    permission_grants = RolePermissionSerializer(many=True, read_only=True)

    class Meta:
        model = Role
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")


class EmployeeRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeRole
        fields = "__all__"
        read_only_fields = ("id", "created_at")
