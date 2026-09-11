from django.db.models import Count, Q
from django.http import FileResponse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response

from audit.services import record
from .models import AnswerOption, Assessment, AssessmentAttempt, Certificate, Course, CourseAssignment, CourseCategory, CourseModule, Lesson, Question
from .permissions import is_learning_manager
from .serializers import (AnswerOptionAdminSerializer, AssessmentSerializer,
                          AttemptSerializer, CertificateSerializer,
                          AssignmentSerializer, AudienceSerializer,
                          CourseCategorySerializer, CourseDetailSerializer,
                          CourseListSerializer, CourseModuleSerializer,
                          CourseWriteSerializer, LessonProgressSerializer,
                          LessonSerializer, QuestionAdminSerializer)
from .services import complete_lesson, review_attempt, start_assignment, start_attempt, submit_attempt
from .integrations import provision_course_assignment


class ManagerWriteMixin:
    def _check_manager(self):
        if not is_learning_manager(self.request.user):
            raise PermissionDenied("Действие доступно руководителю или администратору обучения")

    def create(self, request, *args, **kwargs):
        self._check_manager()
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        self._check_manager()
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        self._check_manager()
        return super().destroy(request, *args, **kwargs)


class CourseCategoryViewSet(ManagerWriteMixin, viewsets.ModelViewSet):
    queryset = CourseCategory.objects.all()
    serializer_class = CourseCategorySerializer


class CourseViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        qs = Course.objects.select_related("category", "author", "owner_department").prefetch_related("modules__lessons", "audience_rules").annotate(modules_count=Count("modules", distinct=True), lessons_count=Count("modules__lessons", distinct=True))
        if not is_learning_manager(self.request.user):
            qs = qs.filter(status=Course.Status.PUBLISHED)
        params = self.request.query_params
        if params.get("search"):
            qs = qs.filter(Q(title__icontains=params["search"]) | Q(description__icontains=params["search"]))
        for key in ("category", "status", "is_mandatory"):
            if params.get(key):
                qs = qs.filter(**{key: params[key]})
        return qs

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return CourseWriteSerializer
        return CourseDetailSerializer if self.action == "retrieve" else CourseListSerializer

    def perform_create(self, serializer):
        if not is_learning_manager(self.request.user):
            raise PermissionDenied("Недостаточно прав")
        course = serializer.save()
        record(self.request.user, "learning.course_created", course, request=self.request)

    def perform_update(self, serializer):
        if not is_learning_manager(self.request.user):
            raise PermissionDenied("Недостаточно прав")
        course = serializer.save()
        record(self.request.user, "learning.course_changed", course, request=self.request)

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        if not is_learning_manager(request.user):
            raise PermissionDenied("Недостаточно прав")
        course = self.get_object()
        if not course.modules.filter(lessons__isnull=False).exists():
            raise ValidationError("Для публикации добавьте хотя бы один урок")
        course.status = Course.Status.PUBLISHED
        course.published_at = timezone.now()
        course.save(update_fields=["status", "published_at", "updated_at"])
        record(request.user, "learning.course_published", course, request=request)
        return Response(CourseDetailSerializer(course).data)

    @action(detail=True, methods=["get", "post"])
    def modules(self, request, pk=None):
        course = self.get_object()
        if request.method == "GET":
            return Response(CourseModuleSerializer(course.modules.all(), many=True).data)
        if not is_learning_manager(request.user):
            raise PermissionDenied("Недостаточно прав")
        serializer = CourseModuleSerializer(data={**request.data, "course": course.id})
        serializer.is_valid(raise_exception=True)
        module = serializer.save()
        return Response(CourseModuleSerializer(module).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="audience")
    def audience(self, request, pk=None):
        course = self.get_object()
        if not is_learning_manager(request.user):
            raise PermissionDenied("Недостаточно прав")
        serializer = AudienceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rule = serializer.save(course=course)
        return Response(AudienceSerializer(rule).data, status=status.HTTP_201_CREATED)


class LessonViewSet(viewsets.ModelViewSet):
    serializer_class = LessonSerializer

    def get_queryset(self):
        qs = Lesson.objects.select_related("module__course", "material")
        if is_learning_manager(self.request.user):
            return qs
        employee = getattr(self.request.user, "employee", None)
        return qs.filter(module__course__assignments__employee=employee).distinct() if employee else qs.none()

    def perform_create(self, serializer):
        if not is_learning_manager(self.request.user):
            raise PermissionDenied("Недостаточно прав")
        serializer.save()

    def perform_update(self, serializer):
        if not is_learning_manager(self.request.user):
            raise PermissionDenied("Недостаточно прав")
        serializer.save()

    def perform_destroy(self, instance):
        if not is_learning_manager(self.request.user):
            raise PermissionDenied("Недостаточно прав")
        instance.delete()

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        lesson = self.get_object()
        assignment_id = request.data.get("assignment")
        if not assignment_id:
            raise ValidationError({"assignment": "Обязательное поле"})
        try:
            assignment = CourseAssignment.objects.select_related("employee__user", "course").get(pk=assignment_id)
        except CourseAssignment.DoesNotExist:
            raise ValidationError("Назначение не найдено")
        progress, assignment = complete_lesson(assignment=assignment, lesson=lesson, actor=request.user, confirmed=request.data.get("confirmed", False), time_spent_seconds=request.data.get("time_spent_seconds", 0), request=request)
        return Response({"progress": LessonProgressSerializer(progress).data, "assignment": AssignmentSerializer(assignment).data})


class AssignmentViewSet(viewsets.ModelViewSet):
    serializer_class = AssignmentSerializer

    def get_queryset(self):
        qs = CourseAssignment.objects.select_related("course", "employee__user", "assigned_by", "current_lesson").prefetch_related("lesson_progress__lesson")
        if is_learning_manager(self.request.user):
            return qs
        employee = getattr(self.request.user, "employee", None)
        return qs.filter(employee=employee) if employee else qs.none()

    def perform_create(self, serializer):
        if not is_learning_manager(self.request.user):
            raise PermissionDenied("Назначать обучение может только руководитель")
        course = serializer.validated_data["course"]
        if course.status != Course.Status.PUBLISHED:
            raise ValidationError("Назначить можно только опубликованный курс")
        assignment = serializer.save(assigned_by=self.request.user)
        provision_course_assignment(assignment, create_task=str(self.request.data.get("create_task", "")).lower() in {"1", "true", "yes"})
        record(self.request.user, "learning.course_assigned", assignment, new_values={"employee_id": assignment.employee_id}, request=self.request)

    def perform_update(self, serializer):
        if not is_learning_manager(self.request.user):
            raise PermissionDenied("Недостаточно прав")
        serializer.save()

    @action(detail=False, methods=["get"])
    def my(self, request):
        employee = getattr(request.user, "employee", None)
        qs = self.get_queryset().filter(employee=employee) if employee else CourseAssignment.objects.none()
        return Response(AssignmentSerializer(qs, many=True).data)

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        assignment = self.get_object()
        assignment = start_assignment(assignment=assignment, actor=request.user, request=request)
        return Response(AssignmentSerializer(assignment).data)


class AssessmentViewSet(ManagerWriteMixin, viewsets.ModelViewSet):
    serializer_class = AssessmentSerializer

    def get_queryset(self):
        qs = Assessment.objects.select_related("course").annotate(questions_count=Count("questions", distinct=True))
        if is_learning_manager(self.request.user):
            filtered = qs
        else:
            employee = getattr(self.request.user, "employee", None)
            filtered = qs.filter(is_active=True, course__assignments__employee=employee).distinct() if employee else qs.none()
        if self.request.query_params.get("course"):
            filtered = filtered.filter(course_id=self.request.query_params["course"])
        return filtered

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        assessment = self.get_object()
        assignment_id = request.data.get("assignment")
        if not assignment_id:
            raise ValidationError({"assignment": "Обязательное поле"})
        try:
            assignment = CourseAssignment.objects.select_related("employee__user", "course").get(pk=assignment_id)
        except CourseAssignment.DoesNotExist:
            raise ValidationError("Назначение не найдено")
        attempt = start_attempt(assessment=assessment, assignment=assignment, actor=request.user, request=request)
        return Response(AttemptSerializer(attempt).data, status=status.HTTP_201_CREATED)


class QuestionViewSet(ManagerWriteMixin, viewsets.ModelViewSet):
    queryset = Question.objects.select_related("assessment").prefetch_related("options")
    serializer_class = QuestionAdminSerializer


class AnswerOptionViewSet(ManagerWriteMixin, viewsets.ModelViewSet):
    queryset = AnswerOption.objects.select_related("question")
    serializer_class = AnswerOptionAdminSerializer


class AttemptViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AttemptSerializer

    def get_queryset(self):
        qs = AssessmentAttempt.objects.select_related("assessment", "assignment", "employee__user").prefetch_related("questions__options", "responses__selected_options", "responses__question")
        if is_learning_manager(self.request.user):
            return qs
        employee = getattr(self.request.user, "employee", None)
        return qs.filter(employee=employee) if employee else qs.none()

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        attempt = self.get_object()
        answers = request.data.get("answers")
        if not isinstance(answers, list):
            raise ValidationError({"answers": "Ожидается список ответов"})
        attempt = submit_attempt(attempt=attempt, actor=request.user, answers=answers, request=request)
        return Response(AttemptSerializer(attempt).data)

    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        if not is_learning_manager(request.user):
            raise PermissionDenied("Ручная проверка доступна руководителю")
        reviews = request.data.get("reviews")
        if not isinstance(reviews, list):
            raise ValidationError({"reviews": "Ожидается список оценок"})
        attempt = review_attempt(attempt=self.get_object(), reviewer=request.user, reviews=reviews, comment=request.data.get("comment", ""), request=request)
        return Response(AttemptSerializer(attempt).data)

    @action(detail=False, methods=["get"])
    def my(self, request):
        employee = getattr(request.user, "employee", None)
        qs = self.get_queryset().filter(employee=employee) if employee else AssessmentAttempt.objects.none()
        return Response(AttemptSerializer(qs, many=True).data)


class CertificateViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CertificateSerializer

    def get_queryset(self):
        qs = Certificate.objects.select_related("employee__user", "course", "assignment", "issued_by")
        if is_learning_manager(self.request.user):
            return qs
        employee = getattr(self.request.user, "employee", None)
        return qs.filter(employee=employee) if employee else qs.none()

    @action(detail=False, methods=["get"])
    def my(self, request):
        employee = getattr(request.user, "employee", None)
        qs = self.get_queryset().filter(employee=employee) if employee else Certificate.objects.none()
        return Response(CertificateSerializer(qs, many=True).data)

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        if not is_learning_manager(request.user):
            raise PermissionDenied("Отзывать сертификаты может только руководитель")
        certificate = self.get_object()
        if certificate.status != Certificate.Status.REVOKED:
            certificate.status = Certificate.Status.REVOKED
            certificate.save(update_fields=["status"])
            record(request.user, "learning.certificate_revoked", certificate, request=request)
        return Response(CertificateSerializer(certificate).data)

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        certificate = self.get_object()
        if not certificate.file:
            raise NotFound("Файл сертификата не сформирован")
        record(request.user, "learning.certificate_downloaded", certificate, request=request)
        return FileResponse(certificate.file.open("rb"), as_attachment=True, filename=f"{certificate.certificate_number}.pdf", content_type="application/pdf")
