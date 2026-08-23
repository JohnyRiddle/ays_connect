import uuid

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from access_control.models import Scope
from .automation import RecurrenceService, TaskTemplateService
from .automation_serializers import (
    OccurrenceSerializer, OccurrenceSkipSerializer, RecurrenceSerializer,
    SavedViewSerializer, TaskTemplateSerializer, TemplateCreateTaskSerializer,
)
from .exceptions import TaskBusinessError
from .models import TaskOccurrence, TaskRecurrenceRule, TaskSavedView, TaskTemplate
from .policies import TaskAccessPolicy
from .serializers import TaskDetailSerializer
from .ux import SavedViewService


class EmployeeContextMixin:
    def actor(self): return self.request.user.employee
    def correlation_id(self):
        raw = self.request.headers.get("X-Correlation-ID")
        return uuid.UUID(raw) if raw else uuid.uuid4()
    def require(self, permission):
        if not self.request.user.is_superuser and not TaskAccessPolicy.allows(employee=self.actor(), permission=permission):
            raise TaskBusinessError("Недостаточно прав.", code="task_permission_denied")

    def scoped_templates(self, permission):
        queryset = TaskTemplate.objects.select_related("responsible_target", "executor_target", "org_unit", "legal_entity", "location", "created_by").prefetch_related("checklist_links__checklist_template")
        if self.request.user.is_superuser: return queryset
        query = Q(pk__in=[])
        for grant in TaskAccessPolicy._grants(self.actor(), permission):
            for scope in grant.role.permission_grants.filter(permission__code=permission).values_list("scope", flat=True):
                if scope == Scope.GLOBAL: return queryset
                if scope == Scope.ORG_UNIT: query |= Q(org_unit_id=grant.org_unit_id or self.actor().org_unit_id)
                elif scope == Scope.LEGAL_ENTITY: query |= Q(legal_entity_id=grant.legal_entity_id or self.actor().legal_entity_id)
                elif scope in {Scope.OWN, Scope.PARTICIPATING}: query |= Q(created_by=self.actor())
        return queryset.filter(query).distinct()


class TaskTemplateViewSet(EmployeeContextMixin, viewsets.GenericViewSet):
    serializer_class = TaskTemplateSerializer

    def get_queryset(self): return self.scoped_templates("task_template.view")
    def list(self, request):
        self.require("task_template.view")
        page = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response(self.get_serializer(page, many=True).data)
    def retrieve(self, request, pk=None):
        self.require("task_template.view")
        return Response(self.get_serializer(self.get_object()).data)
    def create(self, request):
        serializer = self.get_serializer(data=request.data); serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data); checklists = data.pop("checklist_templates", [])
        template = TaskTemplateService.create(actor=self.actor(), actor_user=request.user, checklist_templates=checklists, correlation_id=self.correlation_id(), **data)
        return Response(self.get_serializer(template).data, status=201)
    def partial_update(self, request, pk=None):
        template = self.get_object()
        serializer = self.get_serializer(data=request.data, partial=True); serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data); checklists = data.pop("checklist_templates", None)
        template = TaskTemplateService.update(template=template, actor=self.actor(), actor_user=request.user, checklist_templates=checklists, correlation_id=self.correlation_id(), **data)
        return Response(self.get_serializer(template).data)
    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        return Response(self.get_serializer(TaskTemplateService.deactivate(template=self.get_object(), actor=self.actor(), actor_user=request.user, correlation_id=self.correlation_id())).data)
    @action(detail=True, methods=["post"], url_path="create-task")
    def create_task(self, request, pk=None):
        serializer = TemplateCreateTaskSerializer(data=request.data); serializer.is_valid(raise_exception=True)
        task = TaskTemplateService.create_task(template=self.get_object(), actor=self.actor(), actor_user=request.user, correlation_id=self.correlation_id(), **serializer.validated_data)
        return Response(TaskDetailSerializer(task, context={"request": request}).data, status=201)


class RecurrenceViewSet(EmployeeContextMixin, viewsets.GenericViewSet):
    serializer_class = RecurrenceSerializer

    def get_queryset(self):
        template_ids = self.scoped_templates("task_recurrence.view").values("pk")
        return TaskRecurrenceRule.objects.select_related("task_template", "created_by").filter(task_template_id__in=template_ids).annotate(failed_occurrences_count_value=Count("occurrences", filter=Q(occurrences__status=TaskOccurrence.Status.FAILED)))
    def list(self, request):
        self.require("task_recurrence.view")
        page = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response(self.get_serializer(page, many=True).data)
    def retrieve(self, request, pk=None):
        self.require("task_recurrence.view")
        return Response(self.get_serializer(self.get_object()).data)
    def create(self, request):
        serializer = self.get_serializer(data=request.data); serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data); timezone_name = data.pop("timezone")
        template = data["task_template"]
        if not self.scoped_templates("task_recurrence.manage").filter(pk=template.pk).exists():
            raise TaskBusinessError("Шаблон задачи недоступен.", code="task_permission_denied")
        rule = RecurrenceService.create(actor=self.actor(), actor_user=request.user, timezone_name=timezone_name, correlation_id=self.correlation_id(), **data)
        return Response(self.get_serializer(rule).data, status=201)
    def partial_update(self, request, pk=None):
        rule = self.get_object(); serializer = self.get_serializer(data=request.data, partial=True); serializer.is_valid(raise_exception=True)
        rule = RecurrenceService.update(rule=rule, actor=self.actor(), actor_user=request.user, correlation_id=self.correlation_id(), **serializer.validated_data)
        return Response(self.get_serializer(rule).data)
    @action(detail=True, methods=["post"])
    def pause(self, request, pk=None):
        return Response(self.get_serializer(RecurrenceService.pause(rule=self.get_object(), actor=self.actor(), actor_user=request.user, correlation_id=self.correlation_id())).data)
    @action(detail=True, methods=["post"])
    def resume(self, request, pk=None):
        return Response(self.get_serializer(RecurrenceService.resume(rule=self.get_object(), actor=self.actor(), actor_user=request.user, correlation_id=self.correlation_id())).data)
    @action(detail=True, methods=["get"])
    def occurrences(self, request, pk=None):
        queryset = self.get_object().occurrences.select_related("task", "skipped_by")
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response(OccurrenceSerializer(page, many=True).data)


class OccurrenceViewSet(EmployeeContextMixin, viewsets.GenericViewSet):
    serializer_class = OccurrenceSerializer

    def get_queryset(self):
        template_ids = self.scoped_templates("task_recurrence.view").values("pk")
        return TaskOccurrence.objects.select_related("recurrence_rule", "task").filter(recurrence_rule__task_template_id__in=template_ids)
    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        occurrence = RecurrenceService.retry_occurrence(occurrence=self.get_object(), actor=self.actor(), actor_user=request.user)
        return Response(self.get_serializer(occurrence).data)
    @action(detail=True, methods=["post"])
    def skip(self, request, pk=None):
        serializer = OccurrenceSkipSerializer(data=request.data); serializer.is_valid(raise_exception=True)
        occurrence = RecurrenceService.skip_occurrence(occurrence=self.get_object(), actor=self.actor(), actor_user=request.user, **serializer.validated_data)
        return Response(self.get_serializer(occurrence).data)


class SavedViewViewSet(EmployeeContextMixin, viewsets.GenericViewSet):
    serializer_class = SavedViewSerializer
    def get_queryset(self): return TaskSavedView.objects.filter(owner=self.actor(), is_active=True)
    def list(self, request):
        page = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response(self.get_serializer(page, many=True).data)
    def retrieve(self, request, pk=None): return Response(self.get_serializer(self.get_object()).data)
    def create(self, request):
        serializer = self.get_serializer(data=request.data); serializer.is_valid(raise_exception=True)
        view = SavedViewService.create(owner=self.actor(), **serializer.validated_data)
        return Response(self.get_serializer(view).data, status=201)
    def partial_update(self, request, pk=None):
        serializer = self.get_serializer(data=request.data, partial=True); serializer.is_valid(raise_exception=True)
        view = SavedViewService.update(view=self.get_object(), owner=self.actor(), **serializer.validated_data)
        return Response(self.get_serializer(view).data)
    def destroy(self, request, pk=None):
        SavedViewService.deactivate(view=self.get_object(), owner=self.actor())
        return Response(status=204)
