from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from employees.models import Employee
from .models import LegalEntity, Location, LocationResponsibility, OrgUnit
from .object_policies import LocationAccessPolicy, OPERATIONS
from .object_services import ObjectService


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) - set(self.fields):
            raise serializers.ValidationError({"non_field_errors": ["Переданы недопустимые поля."]})
        return super().to_internal_value(data)


class RelatedID(serializers.UUIDField):
    def __init__(self, model, **kwargs):
        self.model = model
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        pk = super().to_internal_value(data)
        value = self.model.objects.filter(pk=pk).first()
        if value is None:
            raise NotFound()
        ObjectService.relation(self.context["request"].user, value, self.model)
        return value


class ObjectInput(StrictSerializer):
    name = serializers.CharField(max_length=200)
    business_type = serializers.ChoiceField(choices=Location.BusinessType.choices)
    timezone = serializers.CharField(max_length=64)
    parent = RelatedID(Location, required=False, allow_null=True)
    address = serializers.CharField(max_length=500, required=False, allow_blank=True)
    legal_entity = RelatedID(LegalEntity, required=False, allow_null=True)
    org_unit = RelatedID(OrgUnit, required=False, allow_null=True)
    contacts = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    work_schedule = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    description = serializers.CharField(max_length=10000, required=False, allow_blank=True)
    manager = RelatedID(Employee, required=False, allow_null=True)
    technical = RelatedID(Employee, required=False, allow_null=True)
    confirm_duplicate = serializers.BooleanField(required=False)


class VersionInput(StrictSerializer):
    version = serializers.IntegerField(min_value=1)


class LifecycleInput(VersionInput):
    action = serializers.ChoiceField(choices=["operate", "seasonal_close", "close", "reopen", "archive", "restore"])
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)


class ResponsibilityInput(VersionInput):
    role = serializers.ChoiceField(choices=LocationResponsibility.Role.choices)
    employee = RelatedID(Employee, allow_null=True)


class ZoneInput(VersionInput):
    name = serializers.CharField(max_length=200)
    description = serializers.CharField(max_length=10000, required=False, allow_blank=True)


class MoveInput(VersionInput):
    parent = RelatedID(Location, allow_null=True)


class EditInput(VersionInput):
    name = serializers.CharField(max_length=200, required=False)
    business_type = serializers.ChoiceField(choices=Location.BusinessType.choices, required=False)
    timezone = serializers.CharField(max_length=64, required=False)
    address = serializers.CharField(max_length=500, required=False, allow_blank=True)
    org_unit = RelatedID(OrgUnit, required=False, allow_null=True)
    contacts = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    work_schedule = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    description = serializers.CharField(max_length=10000, required=False, allow_blank=True)


class ObjectOutput(serializers.ModelSerializer):
    available_actions = serializers.SerializerMethodField()
    parent_name = serializers.SerializerMethodField()
    legal_entity_name = serializers.SerializerMethodField()
    org_unit_name = serializers.SerializerMethodField()

    class Meta:
        model = Location
        fields = ("id", "code", "name", "node_kind", "business_type", "business_status", "parent", "parent_name", "address", "timezone", "legal_entity", "legal_entity_name", "org_unit", "org_unit_name", "contacts", "work_schedule", "description", "is_archived", "version", "created_at", "updated_at", "available_actions")

    def get_available_actions(self, obj):
        return [op for op in OPERATIONS if LocationAccessPolicy.allows(self.context["request"].user, f"location.{op}", obj)]

    def get_parent_name(self, obj):
        return obj.parent.name if obj.parent_id and LocationAccessPolicy.allows(self.context["request"].user, "location.view", obj.parent) else None

    def get_legal_entity_name(self, obj):
        if obj.legal_entity_id:
            try:
                ObjectService.relation(self.context["request"].user, obj.legal_entity, LegalEntity)
                return obj.legal_entity.name
            except NotFound:
                pass
        return None

    def get_org_unit_name(self, obj):
        if obj.org_unit_id:
            try:
                ObjectService.relation(self.context["request"].user, obj.org_unit, OrgUnit)
                return obj.org_unit.name
            except NotFound:
                pass
        return None

    def to_representation(self, obj):
        data = super().to_representation(obj)
        for field in ("parent", "legal_entity", "org_unit"):
            value = getattr(obj, field)
            if value:
                try:
                    ObjectService.relation(self.context["request"].user, value, value.__class__)
                except NotFound:
                    data[field] = None
        return data


class ObjectViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = ObjectOutput
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        queryset = LocationAccessPolicy.visible(self.request.user).filter(node_kind__in=["object", "zone"]).select_related("parent", "legal_entity", "org_unit").order_by("name", "id")
        return queryset

    def input(self, serializer, data):
        value = serializer(data=data, context={"request": self.request})
        value.is_valid(raise_exception=True)
        return value.validated_data

    def call(self, method, **data):
        try:
            return method(user=self.request.user, **data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
        except APIException:
            raise
        except Exception as exc:
            import logging
            logging.getLogger(__name__).error("Location command failed: %s", type(exc).__name__)
            raise APIException("Не удалось сохранить изменения. Повторите запрос.") from None

    def output(self, item, status=200):
        return Response(self.get_serializer(item).data, status=status)

    def list(self, request):
        qs = self.get_queryset().filter(node_kind="object")
        if request.query_params.get("search"):
            text = request.query_params["search"][:200]
            qs = qs.filter(Q(name__icontains=text) | Q(code__icontains=text) | Q(address__icontains=text))
        for key in ("business_type", "business_status", "legal_entity", "parent"):
            if request.query_params.get(key):
                field = serializers.UUIDField() if key in {"legal_entity", "parent"} else serializers.ChoiceField(choices=Location.BusinessType.values if key == "business_type" else Location.BusinessStatus.values)
                qs = qs.filter(**{key: field.run_validation(request.query_params[key])})
        archived = request.query_params.get("archived", "false")
        if archived not in {"true", "false", "all"}:
            raise serializers.ValidationError({"archived": "Используйте true, false или all."})
        if archived != "all":
            qs = qs.filter(is_archived=archived == "true")
        if request.query_params.get("geography"):
            pk = serializers.UUIDField().run_validation(request.query_params["geography"])
            geography = LocationAccessPolicy.visible(request.user).filter(pk=pk, node_kind__in=["geography", "site"]).first()
            if geography is None:
                raise NotFound()
            ids, frontier = {pk}, {pk}
            while frontier:
                found = set(Location.objects.filter(parent_id__in=frontier).values_list("pk", flat=True)) - ids
                ids.update(found)
                frontier = found
            qs = qs.filter(pk__in=ids)
        if request.query_params.get("responsible"):
            pk = serializers.UUIDField().run_validation(request.query_params["responsible"])
            from employees.onboarding_api import visible_employees
            if not visible_employees(request.user, "people.directory.view").filter(pk=pk).exists():
                raise NotFound()
            from django.utils import timezone
            qs = qs.filter(responsibilities__employee_id=pk, responsibilities__valid_to__isnull=True, responsibilities__valid_from__lte=timezone.now(), responsibilities__employee__is_active=True).distinct()
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    def retrieve(self, request, pk=None):
        return self.output(self.get_object())

    def create(self, request):
        # Check capability before resolving any user-supplied IDs.
        if not request.user.is_superuser and not LocationAccessPolicy.grants(request.user, "location.create").exists():
            raise PermissionDenied()
        item, created = self.call(ObjectService.create, key=request.headers.get("Idempotency-Key", ""), data=self.input(ObjectInput, request.data))
        return self.output(item, 201 if created else 200)

    def partial_update(self, request, pk=None):
        data = self.input(EditInput, request.data)
        version = data.pop("version")
        return self.output(self.call(ObjectService.edit, location=self.get_object(), version=version, data=data))

    @action(detail=True, methods=["post"])
    def lifecycle(self, request, pk=None):
        return self.output(self.call(ObjectService.lifecycle, location=self.get_object(), **self.input(LifecycleInput, request.data)))

    @action(detail=True, methods=["post"])
    def responsible(self, request, pk=None):
        return self.output(self.call(ObjectService.responsibility, location=self.get_object(), **self.input(ResponsibilityInput, request.data)))

    @action(detail=True, methods=["get", "post"])
    def zones(self, request, pk=None):
        location = self.get_object()
        if request.method == "POST":
            return self.output(self.call(ObjectService.zone, parent=location, **self.input(ZoneInput, request.data)), 201)
        qs = self.get_queryset().filter(pk__in=LocationAccessPolicy.descendants(location)).exclude(pk=location.pk)
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    @action(detail=True, methods=["post"])
    def move(self, request, pk=None):
        return self.output(self.call(ObjectService.move, location=self.get_object(), **self.input(MoveInput, request.data)))

    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        from audit.models import AuditEvent
        location = self.get_object()
        qs = AuditEvent.objects.filter(entity_type="Location", entity_id=str(location.pk), action__startswith="location.").order_by("-created_at", "-id")
        # Actor IDs/names and responsibility employees are not disclosed by this feed.
        page = self.paginate_queryset(qs)
        safe = {"name", "business_status", "is_archived", "reason", "role", "timezone", "business_type", "address", "description", "contacts", "work_schedule"}
        return self.get_paginated_response([{"id": row.pk, "action": row.action, "created_at": row.created_at,
            "old": {key: value for key, value in row.old_values.items() if key in safe},
            "new": {key: value for key, value in row.new_values.items() if key in safe}} for row in page])

    @action(detail=True, methods=["get"])
    def responsibilities(self, request, pk=None):
        from employees.onboarding_api import visible_employees
        location = self.get_object()
        visible = visible_employees(request.user, "people.directory.view")
        qs = LocationResponsibility.objects.filter(location=location, employee_id__in=visible.values("pk")).select_related("employee").order_by("-valid_from", "id")
        page = self.paginate_queryset(qs)
        return self.get_paginated_response([{"id": row.pk, "role": row.role, "employee": row.employee_id,
            "employee_name": row.employee.display_name, "valid_from": row.valid_from, "valid_to": row.valid_to, "end_reason": row.end_reason} for row in page])

    @action(detail=False, methods=["get"])
    def capabilities(self, request):
        contexts = {None}
        for permission in ("location.create", "location.view"):
            contexts.update(grant.legal_entity_id for grant in LocationAccessPolicy.grants(request.user, permission) if grant.legal_entity_id)
        global_create = any(LocationAccessPolicy.create_context(request.user, Location(legal_entity_id=context)) and
            LocationAccessPolicy.create_context(request.user, Location(legal_entity_id=context), "location.view") for context in contexts)
        return Response({"can_create": global_create, "business_types": [{"value": key, "label": label} for key, label in Location.BusinessType.choices]})

    @action(detail=False, methods=["get"])
    def tree(self, request):
        qs = self.get_queryset()
        page = self.paginate_queryset(qs)
        # Flat parent IDs are masked by ObjectOutput when parent is invisible.
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    @action(detail=False, methods=["get"], url_path="move-targets")
    def move_targets(self, request):
        source_id = serializers.UUIDField().run_validation(request.query_params.get("source"))
        source = self.get_queryset().filter(pk=source_id).first()
        if source is None:
            raise NotFound()
        ObjectService.authorize(request.user, "location.move", source)
        kinds = ["object", "zone"] if source.node_kind == "zone" else ["geography", "site"]
        qs = LocationAccessPolicy.visible(request.user).filter(LocationAccessPolicy.query(request.user, "location.move"), node_kind__in=kinds, is_archived=False, is_active=True).exclude(pk__in=LocationAccessPolicy.descendants(source)).order_by("name", "id")
        if request.query_params.get("search"):
            qs = qs.filter(name__icontains=request.query_params["search"][:200])
        page = self.paginate_queryset(qs.values("id", "name"))
        return self.get_paginated_response(page)

    @action(detail=False, methods=["get"])
    def lookups(self, request):
        from employees.onboarding_api import visible_employees
        from access_control.services import PermissionService
        user = request.user
        def organization(model):
            return [{"id": str(row.pk), "name": row.name} for row in ObjectService.organization_visible(user, model).filter(is_active=True).order_by("name")]
        # SQL-scoped location/employee lookups, no hidden totals.
        return Response({"parents": list(LocationAccessPolicy.visible(user).filter(node_kind__in=["geography", "site"], is_archived=False).values("id", "name", "timezone")),
            "legal_entities": organization(LegalEntity), "org_units": organization(OrgUnit),
            "employees": [{"id": str(row.pk), "name": row.display_name} for row in visible_employees(user, "people.directory.view").filter(is_active=True).order_by("last_name", "id")[:200]]})

    @action(detail=True, methods=["get"])
    def related(self, request, pk=None):
        from employees.onboarding_api import visible_employees
        from work_tasks.models import Task
        from work_tasks.policies import TaskAccessPolicy
        from service_requests.models import ServiceRequest
        from service_requests.policies import ServiceRequestAccessPolicy
        from projects.policies import ProjectAccessPolicy
        from projects.models import Project
        from employees.models import EmployeeAssignment
        ids = LocationAccessPolicy.descendants(self.get_object())
        actor = getattr(request.user, "employee", None)
        tasks = Task.objects.all() if request.user.is_superuser else Task.objects.filter(TaskAccessPolicy.visibility_query(employee=actor))
        tasks = tasks.filter(location_id__in=ids).distinct()
        requests = ServiceRequest.objects.all() if request.user.is_superuser else ServiceRequest.objects.filter(ServiceRequestAccessPolicy.visibility_query(employee=actor))
        projects = Project.objects.all() if request.user.is_superuser else ProjectAccessPolicy.visible_to(actor)
        from django.utils import timezone
        now = timezone.now()
        assignments = EmployeeAssignment.objects.filter(location_id__in=ids, status="active", valid_from__lte=now).filter(Q(valid_to__isnull=True) | Q(valid_to__gt=now))
        people = visible_employees(request.user, "people.directory.view").filter(is_active=True, pk__in=assignments.values("employee_id"))
        kind = request.query_params.get("kind", "tasks")
        if kind == "tasks":
            qs, fields = tasks.order_by("-created_at", "id"), ("id", "number", "title", "status")
        elif kind == "requests":
            qs, fields = requests.filter(location_id__in=ids).order_by("-created_at", "id"), ("id", "number", "subject", "status")
        elif kind in {"projects", "participating_projects"}:
            qs = projects.filter(location_id__in=ids) if kind == "projects" else projects.filter(task_links__task_id__in=tasks.values("pk"), task_links__is_active=True).exclude(location_id__in=ids)
            qs, fields = qs.distinct().order_by("-created_at", "id"), ("id", "number", "name", "status")
        elif kind == "people":
            qs, fields = people.distinct().order_by("last_name", "id"), ("id", "employee_number", "first_name", "last_name")
        else:
            raise serializers.ValidationError("Недопустимый вид связанных данных.")
        page = self.paginate_queryset(qs.values(*fields))
        return self.get_paginated_response(page)
