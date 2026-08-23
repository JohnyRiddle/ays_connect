from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from access_control.permissions import InternalAPIPermission
from .models import LegalEntity, Location, OrgUnit
from .services import OrgUnitService


class LegalEntitySerializer(serializers.ModelSerializer):
    class Meta:
        model = LegalEntity
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")


class OrgUnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrgUnit
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")


class LegalEntityViewSet(viewsets.ModelViewSet):
    queryset = LegalEntity.objects.all().order_by("name")
    serializer_class = LegalEntitySerializer
    permission_classes = (InternalAPIPermission,)
    permission_domain = "organization"


class OrgUnitViewSet(viewsets.ModelViewSet):
    queryset = OrgUnit.objects.select_related("parent", "legal_entity", "manager_position", "manager_employee").order_by("name")
    serializer_class = OrgUnitSerializer
    permission_classes = (InternalAPIPermission,)
    permission_domain = "organization"

    def perform_create(self, serializer):
        serializer.instance = OrgUnitService.create(actor_user=self.request.user, **serializer.validated_data)

    @action(detail=True, methods=["post"])
    def move(self, request, pk=None):
        unit = self.get_object()
        parent_id = request.data.get("parent_id")
        parent = OrgUnit.objects.get(pk=parent_id) if parent_id else None
        moved = OrgUnitService.move(unit=unit, parent=parent, actor_user=request.user)
        return Response(self.get_serializer(moved).data)


class LocationViewSet(viewsets.ModelViewSet):
    queryset = Location.objects.select_related("parent", "legal_entity").order_by("name")
    serializer_class = LocationSerializer
    permission_classes = (InternalAPIPermission,)
    permission_domain = "location"
