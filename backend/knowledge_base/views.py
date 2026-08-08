from datetime import timedelta
from django.db.models import F, Q
from django.http import FileResponse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response

from audit.services import record
from .access import accessible_materials, can_download, can_manage, employee_for, is_manager
from .models import (KnowledgeCategory, KnowledgeMaterial, MaterialAccessRule,
                     MaterialAcknowledgmentAssignment, MaterialFavorite,
                     MaterialTag, MaterialVersion, MaterialView)
from .serializers import (AccessRuleSerializer, AcknowledgmentSerializer,
                          CategorySerializer, MaterialDetailSerializer,
                          MaterialListSerializer, MaterialWriteSerializer,
                          TagSerializer, VersionCreateSerializer,
                          VersionSerializer)
from .services import publish_version
from notifications.models import Notification
from tasks.models import Task, TaskHistory
from learning.integrations import notify_once


class ManagerWriteMixin:
    def _check_write(self):
        if not is_manager(self.request.user):
            raise PermissionDenied("Действие доступно руководителю или администратору")

    def create(self, request, *args, **kwargs):
        self._check_write()
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        self._check_write()
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        self._check_write()
        return super().destroy(request, *args, **kwargs)


class CategoryViewSet(ManagerWriteMixin, viewsets.ModelViewSet):
    queryset = KnowledgeCategory.objects.all()
    serializer_class = CategorySerializer


class TagViewSet(ManagerWriteMixin, viewsets.ModelViewSet):
    queryset = MaterialTag.objects.all()
    serializer_class = TagSerializer


class MaterialViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        user = self.request.user
        qs = accessible_materials(user).select_related("category", "owner", "owner_department", "current_version").prefetch_related("tags", "access_rules", "versions")
        if not is_manager(user):
            qs = qs.filter(Q(status=KnowledgeMaterial.Status.PUBLISHED) | Q(owner=user))
        params = self.request.query_params
        if params.get("search"):
            term = params["search"]
            qs = qs.filter(Q(title__icontains=term) | Q(description__icontains=term) | Q(current_version__content__icontains=term) | Q(tags__name__icontains=term)).distinct()
        for key in ("category", "material_type", "status", "owner_department"):
            if params.get(key):
                qs = qs.filter(**{key: params[key]})
        if params.get("tag"):
            qs = qs.filter(tags__slug=params["tag"])
        if params.get("featured") == "true":
            qs = qs.filter(is_featured=True)
        if params.get("required") == "true":
            qs = qs.filter(is_required=True)
        employee = employee_for(user)
        if params.get("favorite") == "true" and employee:
            qs = qs.filter(favorites__employee=employee)
        return qs.distinct()

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return MaterialWriteSerializer
        return MaterialDetailSerializer if self.action == "retrieve" else MaterialListSerializer

    def perform_create(self, serializer):
        if not is_manager(self.request.user):
            raise PermissionDenied("Создание материалов доступно руководителю или администратору")
        material = serializer.save()
        record(self.request.user, "knowledge.material_created", material, request=self.request)

    def perform_update(self, serializer):
        if not can_manage(self.request.user, self.get_object()):
            raise PermissionDenied("Недостаточно прав для изменения материала")
        serializer.save()

    def perform_destroy(self, instance):
        if not can_manage(self.request.user, instance):
            raise PermissionDenied("Недостаточно прав для удаления материала")
        instance.delete()

    def retrieve(self, request, *args, **kwargs):
        material = self.get_object()
        employee = employee_for(request.user)
        if employee:
            view, created = MaterialView.objects.get_or_create(material=material, employee=employee, defaults={"version": material.current_version})
            if not created:
                MaterialView.objects.filter(pk=view.pk).update(view_count=F("view_count") + 1, version=material.current_version, viewed_at=timezone.now())
            assignment = MaterialAcknowledgmentAssignment.objects.filter(version=material.current_version, employee=employee, status=MaterialAcknowledgmentAssignment.Status.ASSIGNED).first()
            if assignment:
                assignment.status = assignment.Status.OPENED
                assignment.opened_at = timezone.now()
                assignment.save(update_fields=["status", "opened_at"])
        return Response(self.get_serializer(material).data)

    @action(detail=True, methods=["post"])
    def favorite(self, request, pk=None):
        employee = employee_for(request.user)
        if not employee:
            raise ValidationError("У пользователя нет карточки сотрудника")
        favorite, created = MaterialFavorite.objects.get_or_create(material=self.get_object(), employee=employee)
        if not created:
            favorite.delete()
        return Response({"is_favorite": created})

    @action(detail=True, methods=["get", "post"])
    def versions(self, request, pk=None):
        material = self.get_object()
        if request.method == "GET":
            return Response(VersionSerializer(material.versions.all(), many=True).data)
        if not can_manage(request.user, material):
            raise PermissionDenied("Недостаточно прав для публикации версии")
        serializer = VersionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        version = publish_version(material=material, actor=request.user, data=serializer.validated_data, request=request)
        return Response(VersionSerializer(version).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path=r"versions/(?P<version_id>[^/.]+)/download")
    def download_version(self, request, pk=None, version_id=None):
        material = self.get_object()
        if not can_download(request.user, material):
            raise PermissionDenied("Скачивание материала недоступно")
        try:
            version = material.versions.get(pk=version_id)
        except MaterialVersion.DoesNotExist:
            raise NotFound("Версия не найдена")
        if not version.file:
            raise NotFound("У версии нет файла")
        record(request.user, "knowledge.file_downloaded", version, request=request)
        return FileResponse(version.file.open("rb"), as_attachment=True, filename=version.original_name or version.file.name, content_type=version.content_type or "application/octet-stream")

    @action(detail=True, methods=["post"])
    def acknowledge(self, request, pk=None):
        material = self.get_object()
        employee = employee_for(request.user)
        if not employee or not material.current_version:
            raise ValidationError("Нет доступной версии для ознакомления")
        try:
            assignment = MaterialAcknowledgmentAssignment.objects.get(version=material.current_version, employee=employee)
        except MaterialAcknowledgmentAssignment.DoesNotExist:
            raise PermissionDenied("Ознакомление не назначено")
        if assignment.status in {assignment.Status.CANCELLED, assignment.Status.OVERDUE}:
            raise ValidationError("Назначение нельзя подтвердить в текущем статусе")
        assignment.status = assignment.Status.ACKNOWLEDGED
        assignment.acknowledged_at = timezone.now()
        assignment.opened_at = assignment.opened_at or timezone.now()
        assignment.save(update_fields=["status", "acknowledged_at", "opened_at"])
        if assignment.related_task and assignment.related_task.status not in {Task.Status.CLOSED, Task.Status.COMPLETED, Task.Status.CANCELLED}:
            task = assignment.related_task; old = task.status; task.status = Task.Status.CLOSED; task.completed_at = timezone.now(); task.result_text = "Закрыта автоматически после подтверждения ознакомления"; task.save(update_fields=["status", "completed_at", "result_text", "updated_at"])
            TaskHistory.objects.create(task=task, actor=request.user, action="closed_by_acknowledgment", from_status=old, to_status=task.status, details={"acknowledgment_id": assignment.id})
        record(request.user, "knowledge.material_acknowledged", assignment, new_values={"version_id": assignment.version_id}, request=request)
        return Response(AcknowledgmentSerializer(assignment).data)

    @action(detail=True, methods=["post"], url_path="access-rules")
    def access_rules(self, request, pk=None):
        material = self.get_object()
        if not can_manage(request.user, material):
            raise PermissionDenied("Недостаточно прав")
        serializer = AccessRuleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rule = serializer.save(material=material)
        record(request.user, "knowledge.access_rule_changed", rule, request=request)
        return Response(AccessRuleSerializer(rule).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="assign-acknowledgment")
    def assign_acknowledgment(self, request, pk=None):
        material = self.get_object()
        if not can_manage(request.user, material):
            raise PermissionDenied("Недостаточно прав")
        if not material.current_version:
            raise ValidationError("Сначала опубликуйте версию")
        employee_id = request.data.get("employee")
        if not employee_id:
            raise ValidationError({"employee": "Обязательное поле"})
        assignment, created = MaterialAcknowledgmentAssignment.objects.get_or_create(
            version=material.current_version, employee_id=employee_id,
            defaults={"assigned_by": request.user, "due_at": request.data.get("due_at") or None},
        )
        if created and assignment.employee.user:
            notify_once(recipient=assignment.employee.user, notification_type=Notification.Type.MATERIAL_ACK_REQUIRED, title="Требуется ознакомление", message=f"Ознакомьтесь с «{material.title}».", entity_type="MaterialAcknowledgmentAssignment", entity_id=assignment.id, priority=Notification.Priority.WARNING)
        if str(request.data.get("create_task", "")).lower() in {"1", "true", "yes"} and not assignment.related_task_id and assignment.employee.user:
            deadline = assignment.due_at or timezone.now() + timedelta(days=7)
            task = Task.objects.create(title=f"Ознакомиться с «{material.title}»", description=material.description, creator=request.user, assignee=assignment.employee.user, department=assignment.employee.department, priority=Task.Priority.NORMAL, initial_deadline=deadline, deadline=deadline, acceptance_criteria="Подтвердить ознакомление с актуальной версией", requires_review=False, source=Task.Source.DOCUMENT, status=Task.Status.ASSIGNED, is_demo=assignment.employee.user.is_demo)
            TaskHistory.objects.create(task=task, actor=request.user, action="created_from_document", to_status=task.status, details={"acknowledgment_id": assignment.id})
            assignment.related_task = task; assignment.save(update_fields=["related_task"])
        return Response(AcknowledgmentSerializer(assignment).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @action(detail=False, methods=["get"])
    def required(self, request):
        employee = employee_for(request.user)
        qs = MaterialAcknowledgmentAssignment.objects.none() if not employee else MaterialAcknowledgmentAssignment.objects.filter(employee=employee).exclude(status__in=[MaterialAcknowledgmentAssignment.Status.ACKNOWLEDGED, MaterialAcknowledgmentAssignment.Status.CANCELLED]).select_related("version__material", "assigned_by")
        return Response(AcknowledgmentSerializer(qs, many=True).data)

    @action(detail=False, methods=["get"])
    def recent(self, request):
        employee = employee_for(request.user)
        ids = [] if not employee else MaterialView.objects.filter(employee=employee).order_by("-viewed_at").values_list("material_id", flat=True)[:25]
        qs = self.get_queryset().filter(id__in=ids)
        return Response(MaterialListSerializer(qs, many=True, context={"request": request}).data)

    @action(detail=False, methods=["get"])
    def ttk(self, request):
        qs = self.get_queryset().filter(material_type=KnowledgeMaterial.Type.TTK)
        return Response(MaterialListSerializer(qs, many=True, context={"request": request}).data)
