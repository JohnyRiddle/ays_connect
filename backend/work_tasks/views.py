import uuid

from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .selectors import TaskSelector
from .serializers import (
    CompleteSerializer, DeadlineSerializer, PauseSerializer, ReasonSerializer,
    ReassignSerializer, ReviewSerializer, TaskCreateSerializer,
    TaskDetailSerializer, TaskPatchSerializer, TaskSerializer, VersionSerializer,
)
from .services import TaskService
from access_control.services import PermissionService
from employees.models import Employee
from .activity import TaskActivitySelector
from .collaboration import ChecklistService, CollaborationService
from .collaboration_serializers import (
    AttachmentSerializer, ChecklistItemSerializer, ChecklistTemplateSerializer,
    CommentSerializer, CommentWriteSerializer, ManualChecklistSerializer,
    TaskChecklistSerializer, TemplateApplySerializer, WatcherSerializer,
    WatcherWriteSerializer,
)
from .models import ChecklistTemplate, ChecklistTemplateItem, TaskAttachment, TaskChecklist, TaskChecklistItem, TaskComment, TaskWatcher
from .policies import TaskAccessPolicy
from .ux import TaskUXService


class ProductionTaskViewSet(viewsets.GenericViewSet):
    def _actor(self):
        return self.request.user.employee

    def _correlation_id(self):
        raw = self.request.headers.get("X-Correlation-ID")
        return uuid.UUID(raw) if raw else uuid.uuid4()

    def get_queryset(self):
        if self.request.user.is_superuser:
            queryset = self._all()
        else:
            queryset = TaskSelector.visible_to(self._actor())
        queryset = TaskSelector.apply_saved_or_system_view(queryset, self._actor(), self.request.query_params)
        return TaskSelector.apply_filters(queryset, self.request.query_params)

    @staticmethod
    def _all():
        from .models import Task
        return Task.objects.select_related(*TaskSelector.RELATED)

    def get_serializer_class(self):
        if self.action == "create":
            return TaskCreateSerializer
        if self.action == "partial_update":
            return TaskPatchSerializer
        return TaskDetailSerializer if self.action == "retrieve" else TaskSerializer

    def list(self, request):
        page = self.paginate_queryset(self.get_queryset())
        serializer = TaskSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    def retrieve(self, request, pk=None):
        return Response(TaskDetailSerializer(self.get_object(), context={"request": request}).data)

    def create(self, request):
        serializer = TaskCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = TaskService.create(actor=self._actor(), actor_user=request.user, correlation_id=self._correlation_id(), **serializer.validated_data)
        return Response(TaskDetailSerializer(task, context={"request": request}).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, pk=None):
        serializer = TaskPatchSerializer(data=request.data, partial=False)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        version = data.pop("version")
        task = TaskService.update(task=self.get_object(), actor=self._actor(), actor_user=request.user, version=version, correlation_id=self._correlation_id(), **data)
        return Response(TaskDetailSerializer(task, context={"request": request}).data)

    @action(detail=False, methods=["get"])
    def counters(self, request):
        queryset = self._all() if request.user.is_superuser else None
        return Response(TaskUXService.counters(self._actor(), queryset=queryset))

    def _command(self, request, service, serializer_class=VersionSerializer, **mapping):
        serializer = serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        kwargs = dict(serializer.validated_data)
        for target, source in mapping.items():
            kwargs[target] = kwargs.pop(source)
        task = service(task=self.get_object(), actor=self._actor(), actor_user=request.user, correlation_id=self._correlation_id(), **kwargs)
        return Response(TaskDetailSerializer(task, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None): return self._command(request, TaskService.publish)

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None): return self._command(request, TaskService.start)

    @action(detail=True, methods=["post"])
    def pause(self, request, pk=None): return self._command(request, TaskService.pause, PauseSerializer)

    @action(detail=True, methods=["post"])
    def resume(self, request, pk=None): return self._command(request, TaskService.resume)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None): return self._command(request, TaskService.complete, CompleteSerializer)

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None): return self._command(request, TaskService.accept, ReviewSerializer)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None): return self._command(request, TaskService.reject, ReasonSerializer)

    @action(detail=True, methods=["post"])
    def reopen(self, request, pk=None): return self._command(request, TaskService.reopen, ReasonSerializer)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None): return self._command(request, TaskService.cancel, ReasonSerializer)

    @action(detail=True, methods=["post"])
    def reassign(self, request, pk=None): return self._command(request, TaskService.reassign, ReassignSerializer, new_target="target")

    @action(detail=True, methods=["post"], url_path="deadline")
    def deadline(self, request, pk=None): return self._command(request, TaskService.change_deadline, DeadlineSerializer, new_due_at="due_at")

    @action(detail=True, methods=["get", "post"])
    def comments(self, request, pk=None):
        task = self.get_object()
        if request.method == "GET":
            queryset = task.production_comments.select_related("author", "deleted_by").prefetch_related("mention_records__employee")
            if not (request.user.is_superuser or PermissionService.has_permission(employee=self._actor(), permission="task.comment_internal", obj=task)):
                queryset = queryset.filter(is_internal=False)
            return Response(CommentSerializer(queryset, many=True).data)
        serializer = CommentWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        comment = CollaborationService.add_comment(task=task, actor=self._actor(), actor_user=request.user, correlation_id=self._correlation_id(), **serializer.validated_data)
        return Response(CommentSerializer(comment).data, status=201)

    @action(detail=True, methods=["patch", "delete"], url_path=r"comments/(?P<comment_id>[^/.]+)")
    def comment_detail(self, request, pk=None, comment_id=None):
        task = self.get_object()
        comment = get_object_or_404(TaskComment.objects.select_related("task"), pk=comment_id, task=task)
        if request.method == "DELETE":
            CollaborationService.delete_comment(comment=comment, actor=self._actor(), actor_user=request.user, correlation_id=self._correlation_id())
        else:
            serializer = CommentWriteSerializer(data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            comment = CollaborationService.edit_comment(comment=comment, actor=self._actor(), actor_user=request.user, correlation_id=self._correlation_id(), **serializer.validated_data)
        return Response(CommentSerializer(comment).data)

    @action(detail=True, methods=["get", "post"])
    def attachments(self, request, pk=None):
        task = self.get_object()
        if request.method == "GET":
            return Response(AttachmentSerializer(task.production_attachments.filter(deleted_at__isnull=True).select_related("uploaded_by"), many=True).data)
        attachment = CollaborationService.add_attachment(task=task, actor=self._actor(), actor_user=request.user, uploaded_file=request.FILES.get("file"), correlation_id=self._correlation_id())
        return Response(AttachmentSerializer(attachment).data, status=201)

    @action(detail=True, methods=["delete"], url_path=r"attachments/(?P<attachment_id>[^/.]+)")
    def attachment_detail(self, request, pk=None, attachment_id=None):
        task = self.get_object()
        attachment = get_object_or_404(TaskAttachment, pk=attachment_id, task=task, deleted_at__isnull=True)
        CollaborationService.delete_attachment(attachment=attachment, actor=self._actor(), actor_user=request.user, correlation_id=self._correlation_id())
        return Response(status=204)

    @action(detail=True, methods=["get"], url_path=r"attachments/(?P<attachment_id>[^/.]+)/download")
    def attachment_download(self, request, pk=None, attachment_id=None):
        task = self.get_object()
        attachment = get_object_or_404(TaskAttachment, pk=attachment_id, task=task, deleted_at__isnull=True)
        return FileResponse(attachment.file.open("rb"), as_attachment=True, filename=attachment.original_filename, content_type=attachment.content_type)

    @action(detail=True, methods=["post", "delete"])
    def watch(self, request, pk=None):
        task, actor = self.get_object(), self._actor()
        if request.method == "POST":
            watcher = CollaborationService.add_watcher(task=task, employee=actor, actor=actor, actor_user=request.user, correlation_id=self._correlation_id())
            return Response(WatcherSerializer(watcher).data, status=201)
        CollaborationService.remove_watcher(task=task, employee=actor, actor=actor, actor_user=request.user, correlation_id=self._correlation_id())
        return Response(status=204)

    @action(detail=True, methods=["get", "post"])
    def watchers(self, request, pk=None):
        task = self.get_object()
        if request.method == "GET":
            return Response(WatcherSerializer(task.watcher_records.filter(removed_at__isnull=True).select_related("employee", "added_by"), many=True).data)
        serializer = WatcherWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        watcher = CollaborationService.add_watcher(task=task, employee=serializer.validated_data["employee"], actor=self._actor(), actor_user=request.user, correlation_id=self._correlation_id())
        return Response(WatcherSerializer(watcher).data, status=201)

    @action(detail=True, methods=["delete"], url_path=r"watchers/(?P<employee_id>[^/.]+)")
    def watcher_detail(self, request, pk=None, employee_id=None):
        task = self.get_object()
        employee = get_object_or_404(Employee, pk=employee_id)
        CollaborationService.remove_watcher(task=task, employee=employee, actor=self._actor(), actor_user=request.user, correlation_id=self._correlation_id())
        return Response(status=204)

    @action(detail=True, methods=["get", "post"])
    def checklists(self, request, pk=None):
        task = self.get_object()
        if request.method == "GET":
            queryset = task.production_checklists.filter(removed_at__isnull=True).select_related("source_template", "created_by").prefetch_related("items")
            return Response(TaskChecklistSerializer(queryset, many=True).data)
        serializer = ManualChecklistSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        checklist = ChecklistService.create_manual(task=task, actor=self._actor(), actor_user=request.user, correlation_id=self._correlation_id(), **serializer.validated_data)
        return Response(TaskChecklistSerializer(checklist).data, status=201)

    @action(detail=True, methods=["post"], url_path="checklists/from-template")
    def checklist_from_template(self, request, pk=None):
        serializer = TemplateApplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        checklist = ChecklistService.from_template(task=self.get_object(), template=serializer.validated_data["template"], actor=self._actor(), actor_user=request.user, correlation_id=self._correlation_id())
        return Response(TaskChecklistSerializer(checklist).data, status=201)

    @action(detail=True, methods=["post"], url_path=r"checklists/(?P<checklist_id>[^/.]+)/items")
    def checklist_items(self, request, pk=None, checklist_id=None):
        task = self.get_object()
        checklist = get_object_or_404(TaskChecklist, pk=checklist_id, task=task, removed_at__isnull=True)
        serializer = ChecklistItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = ChecklistService.add_item(checklist=checklist, actor=self._actor(), actor_user=request.user, correlation_id=self._correlation_id(), **serializer.validated_data)
        return Response(ChecklistItemSerializer(item).data, status=201)

    @action(detail=True, methods=["delete"], url_path=r"checklists/(?P<checklist_id>[^/.]+)")
    def checklist_detail(self, request, pk=None, checklist_id=None):
        task = self.get_object()
        checklist = get_object_or_404(TaskChecklist, pk=checklist_id, task=task, removed_at__isnull=True)
        ChecklistService.remove_checklist(checklist=checklist, actor=self._actor(), actor_user=request.user, correlation_id=self._correlation_id())
        return Response(status=204)

    @action(detail=True, methods=["patch"], url_path=r"checklists/(?P<checklist_id>[^/.]+)/items/(?P<item_id>[^/.]+)")
    def checklist_item_detail(self, request, pk=None, checklist_id=None, item_id=None):
        task = self.get_object()
        item = get_object_or_404(TaskChecklistItem, pk=item_id, checklist_id=checklist_id, checklist__task=task, checklist__removed_at__isnull=True)
        serializer = ChecklistItemSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        item = ChecklistService.update_item(item=item, actor=self._actor(), actor_user=request.user, correlation_id=self._correlation_id(), **serializer.validated_data)
        return Response(ChecklistItemSerializer(item).data)

    def _checklist_toggle(self, request, checklist_id, item_id, completed):
        task = self.get_object()
        item = get_object_or_404(TaskChecklistItem, pk=item_id, checklist_id=checklist_id, checklist__task=task, checklist__removed_at__isnull=True)
        item = ChecklistService.set_completed(item=item, actor=self._actor(), actor_user=request.user, completed=completed, comment=request.data.get("comment"), correlation_id=self._correlation_id())
        return Response(ChecklistItemSerializer(item).data)

    @action(detail=True, methods=["post"], url_path=r"checklists/(?P<checklist_id>[^/.]+)/items/(?P<item_id>[^/.]+)/complete")
    def checklist_item_complete(self, request, pk=None, checklist_id=None, item_id=None): return self._checklist_toggle(request, checklist_id, item_id, True)

    @action(detail=True, methods=["post"], url_path=r"checklists/(?P<checklist_id>[^/.]+)/items/(?P<item_id>[^/.]+)/uncomplete")
    def checklist_item_uncomplete(self, request, pk=None, checklist_id=None, item_id=None): return self._checklist_toggle(request, checklist_id, item_id, False)

    @action(detail=True, methods=["get"])
    def activity(self, request, pk=None):
        task = self.get_object()
        return Response(TaskActivitySelector.page(task=task, employee=self._actor(), page=request.query_params.get("page", 1), page_size=request.query_params.get("page_size", 25)))


class ChecklistTemplateViewSet(viewsets.GenericViewSet):
    queryset = ChecklistTemplate.objects.prefetch_related("items").order_by("name")
    serializer_class = ChecklistTemplateSerializer

    def _actor(self): return self.request.user.employee
    def _correlation_id(self):
        raw = self.request.headers.get("X-Correlation-ID")
        return uuid.UUID(raw) if raw else uuid.uuid4()
    def _require(self, permission):
        if not self.request.user.is_superuser and not TaskAccessPolicy.allows(employee=self._actor(), permission=permission):
            from .exceptions import TaskBusinessError
            raise TaskBusinessError("Недостаточно прав.", code="task_permission_denied")
    def list(self, request):
        self._require("checklist_template.view")
        return Response(self.get_serializer(self.get_queryset(), many=True).data)
    def retrieve(self, request, pk=None):
        self._require("checklist_template.view")
        return Response(self.get_serializer(self.get_object()).data)
    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data); items = data.pop("items", [])
        template = ChecklistService.create_template(actor=self._actor(), actor_user=request.user, items=items, correlation_id=self._correlation_id(), **data)
        return Response(self.get_serializer(template).data, status=201)
    def partial_update(self, request, pk=None):
        serializer = self.get_serializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data); items = data.pop("items", None)
        template = ChecklistService.update_template(template=self.get_object(), actor=self._actor(), actor_user=request.user, correlation_id=self._correlation_id(), **data)
        if items is not None:
            template.items.all().delete()
            ChecklistTemplateItem.objects.bulk_create([ChecklistTemplateItem(template=template, **item) for item in items])
        return Response(self.get_serializer(template).data)
