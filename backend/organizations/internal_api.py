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
        read_only_fields = ("id", "parent", "status", "valid_to", "version", "created_at", "updated_at")


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
        moved = OrgUnitService.move(unit=unit, parent=parent, expected_version=int(request.data.get("version",0)), actor_user=request.user)
        return Response(self.get_serializer(moved).data)

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        return Response(self.get_serializer(OrgUnitService.close(unit=self.get_object(),expected_version=int(request.data.get("version",0)),actor_user=request.user,reason=request.data.get("reason",""))).data)

    def perform_destroy(self, instance):
        raise serializers.ValidationError("Подразделения не удаляются физически; используйте close.")

    @action(detail=False, methods=["get"])
    def tree(self, request):
        qs=self.get_queryset()
        if request.query_params.get("legal_entity"): qs=qs.filter(legal_entity=request.query_params["legal_entity"])
        rows=list(qs.values("id","parent_id","code","name","short_name","unit_type","status","sort_order")); children={}
        for row in rows: children.setdefault(row["parent_id"],[]).append(row)
        for values in children.values(): values.sort(key=lambda x:(x["sort_order"],x["name"]))
        def node(row): return {**row,"children":[node(x) for x in children.get(row["id"],[])]}
        return Response([node(x) for x in children.get(None,[])])


class LocationViewSet(viewsets.ModelViewSet):
    queryset = Location.objects.select_related("parent", "legal_entity").order_by("name")
    serializer_class = LocationSerializer
    permission_classes = (InternalAPIPermission,)
    permission_domain = "location"
