from django.db.models import Q
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from access_control.permissions import InternalAPIPermission
from access_control.models import Role
from access_control.serializers import EmployeeRoleSerializer
from access_control.services import RoleService
from .models import AssignmentTarget, Employee, FunctionalGroup, FunctionalGroupMembership, Position
from .services import EmployeeService, FunctionalGroupService


class EmployeeInternalSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)
    class Meta:
        model = Employee
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at", "dismissed_at")


class PositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Position
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")


class FunctionalGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = FunctionalGroup
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")


class AssignmentTargetSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()
    target_type_label = serializers.CharField(source="get_target_type_display", read_only=True)

    class Meta:
        model = AssignmentTarget
        fields = ("id", "target_type", "target_type_label", "display_name", "employee", "position", "org_unit", "functional_group")
        read_only_fields = fields

    def get_display_name(self, obj):
        target = obj.employee or obj.position or obj.org_unit or obj.functional_group
        return getattr(target, "display_name", None) or getattr(target, "name", None) or str(target)


class MembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = FunctionalGroupMembership
        fields = "__all__"
        read_only_fields = ("id", "created_at")


class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.select_related("user", "position_ref", "org_unit", "legal_entity", "primary_location", "manager")
    serializer_class = EmployeeInternalSerializer
    permission_classes = (InternalAPIPermission,)
    permission_domain = "employee"

    def perform_create(self, serializer):
        serializer.instance = EmployeeService.create(actor_user=self.request.user, **serializer.validated_data)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        return Response(self.get_serializer(EmployeeService.deactivate(employee=self.get_object(), actor_user=request.user)).data)

    @action(detail=True, methods=["post"])
    def roles(self, request, pk=None):
        role = Role.objects.get(pk=request.data["role"])
        context = {key: request.data.get(key) for key in ("org_unit_id", "legal_entity_id", "location_id", "active_from", "active_until") if request.data.get(key)}
        assignment = RoleService.assign_role(employee=self.get_object(), role=role, actor_user=request.user, **context)
        return Response(EmployeeRoleSerializer(assignment).data, status=201)


class PositionViewSet(viewsets.ModelViewSet):
    queryset = Position.objects.select_related("org_unit", "legal_entity").order_by("name")
    serializer_class = PositionSerializer
    permission_classes = (InternalAPIPermission,)
    permission_domain = "employee"


class FunctionalGroupViewSet(viewsets.ModelViewSet):
    queryset = FunctionalGroup.objects.select_related("org_unit", "legal_entity", "location").prefetch_related("memberships__employee")
    serializer_class = FunctionalGroupSerializer
    permission_classes = (InternalAPIPermission,)
    permission_domain = "functional_group"

    @action(detail=True, methods=["post"])
    def members(self, request, pk=None):
        serializer = MembershipSerializer(data={**request.data, "group": self.get_object().pk})
        serializer.is_valid(raise_exception=True)
        membership = FunctionalGroupService.add_member(group=self.get_object(), employee=serializer.validated_data["employee"], actor_user=request.user, role=serializer.validated_data.get("role", ""), active_from=serializer.validated_data.get("active_from"), active_until=serializer.validated_data.get("active_until"))
        return Response(MembershipSerializer(membership).data, status=201)


class AssignmentTargetViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AssignmentTargetSerializer
    permission_classes = (InternalAPIPermission,)
    permission_domain = "employee"

    def get_queryset(self):
        queryset = AssignmentTarget.objects.select_related("employee", "position", "org_unit", "functional_group")
        target_type = self.request.query_params.get("target_type")
        if target_type:
            queryset = queryset.filter(target_type=target_type)
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(employee__first_name__icontains=search) | Q(employee__last_name__icontains=search)
                | Q(position__name__icontains=search) | Q(org_unit__name__icontains=search)
                | Q(functional_group__name__icontains=search)
            )
        return queryset.order_by("target_type", "id")
