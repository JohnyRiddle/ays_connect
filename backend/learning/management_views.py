from datetime import timedelta

from django.db.models import Avg, Count, Min, Q
from django.utils import timezone
from rest_framework import serializers
from rest_framework.generics import GenericAPIView, ListAPIView
from rest_framework.response import Response

from employees.models import Employee
from knowledge_base.models import KnowledgeMaterial, MaterialAcknowledgmentAssignment

from .models import AssessmentAttempt, Certificate, CourseAssignment
from .permissions import IsLearningManager
from .serializers import AssignmentSerializer, CertificateSerializer


def company_ids_for(user):
    if user.is_superuser:
        return None
    ids = set(user.role_assignments.exclude(company_id=None).values_list("company_id", flat=True))
    employee = getattr(user, "employee", None)
    if employee:
        ids.add(employee.company_id)
    return ids


def company_filter(user, field):
    ids = company_ids_for(user)
    return Q() if ids is None else Q(**{f"{field}__in": ids})


class LearningSummarySerializer(serializers.Serializer):
    assigned = serializers.IntegerField()
    completed = serializers.IntegerField()
    overdue = serializers.IntegerField()
    completion_rate = serializers.FloatField()
    average_score = serializers.FloatField()
    repeat_attempts = serializers.IntegerField()
    certificates_active = serializers.IntegerField()
    certificates_expiring = serializers.IntegerField()
    certificates_expired = serializers.IntegerField()
    acknowledgments_pending = serializers.IntegerField()


class LearningSummaryView(GenericAPIView):
    permission_classes = [IsLearningManager]
    serializer_class = LearningSummarySerializer

    def get(self, request):
        assignments = CourseAssignment.objects.filter(company_filter(request.user, "employee__company_id"))
        attempts = AssessmentAttempt.objects.filter(company_filter(request.user, "employee__company_id"))
        certificates = Certificate.objects.filter(company_filter(request.user, "employee__company_id"))
        acknowledgments = MaterialAcknowledgmentAssignment.objects.filter(company_filter(request.user, "employee__company_id"))
        assigned = assignments.count()
        completed = assignments.filter(status=CourseAssignment.Status.COMPLETED).count()
        data = {
            "assigned": assigned,
            "completed": completed,
            "overdue": assignments.filter(status=CourseAssignment.Status.OVERDUE).count(),
            "completion_rate": round(completed * 100 / assigned, 1) if assigned else 0,
            "average_score": round(float(attempts.filter(status__in=[AssessmentAttempt.Status.PASSED, AssessmentAttempt.Status.FAILED]).aggregate(value=Avg("score_percent"))["value"] or 0), 1),
            "repeat_attempts": attempts.filter(attempt_number__gt=1).count(),
            "certificates_active": certificates.filter(status=Certificate.Status.ACTIVE).count(),
            "certificates_expiring": certificates.filter(status=Certificate.Status.EXPIRING).count(),
            "certificates_expired": certificates.filter(status=Certificate.Status.EXPIRED).count(),
            "acknowledgments_pending": acknowledgments.exclude(status__in=[MaterialAcknowledgmentAssignment.Status.ACKNOWLEDGED, MaterialAcknowledgmentAssignment.Status.CANCELLED]).count(),
        }
        return Response(self.get_serializer(data).data)


class EmployeeLearningSerializer(serializers.Serializer):
    employee_id = serializers.IntegerField()
    full_name = serializers.CharField()
    department = serializers.CharField(allow_null=True)
    mandatory_courses = serializers.IntegerField()
    completed = serializers.IntegerField()
    overdue = serializers.IntegerField()
    average_score = serializers.FloatField()
    certificates = serializers.IntegerField()
    nearest_expiration = serializers.DateTimeField(allow_null=True)
    acknowledgment_rate = serializers.FloatField()


class EmployeeLearningView(GenericAPIView):
    permission_classes = [IsLearningManager]
    serializer_class = EmployeeLearningSerializer

    def get(self, request):
        employees = Employee.objects.filter(user__isnull=False).filter(company_filter(request.user, "company_id")).select_related("user", "department")
        rows = []
        for employee in employees:
            assignments = employee.course_assignments.all()
            acknowledgments = employee.material_acknowledgments.all()
            ack_total = acknowledgments.count()
            rows.append({
                "employee_id": employee.id,
                "full_name": employee.user.get_full_name(),
                "department": employee.department.name if employee.department else None,
                "mandatory_courses": assignments.filter(is_mandatory=True).count(),
                "completed": assignments.filter(status=CourseAssignment.Status.COMPLETED).count(),
                "overdue": assignments.filter(status=CourseAssignment.Status.OVERDUE).count(),
                "average_score": round(float(employee.assessment_attempts.filter(passed=True).aggregate(value=Avg("score_percent"))["value"] or 0), 1),
                "certificates": employee.certificates.filter(status__in=[Certificate.Status.ACTIVE, Certificate.Status.EXPIRING]).count(),
                "nearest_expiration": employee.certificates.filter(expires_at__gte=timezone.now()).aggregate(value=Min("expires_at"))["value"],
                "acknowledgment_rate": round(acknowledgments.filter(status=MaterialAcknowledgmentAssignment.Status.ACKNOWLEDGED).count() * 100 / ack_total, 1) if ack_total else 100,
            })
        return Response(self.get_serializer(rows, many=True).data)


class OverdueLearningView(ListAPIView):
    permission_classes = [IsLearningManager]
    serializer_class = AssignmentSerializer

    def get_queryset(self):
        return CourseAssignment.objects.filter(
            company_filter(self.request.user, "employee__company_id"),
            status=CourseAssignment.Status.OVERDUE,
        ).select_related("course", "employee__user", "assigned_by", "current_lesson")


class ExpiringCertificatesView(ListAPIView):
    permission_classes = [IsLearningManager]
    serializer_class = CertificateSerializer

    def get_queryset(self):
        return Certificate.objects.filter(
            company_filter(self.request.user, "employee__company_id"),
            status__in=[Certificate.Status.EXPIRING, Certificate.Status.EXPIRED],
        ).select_related("course", "employee__user", "assignment", "issued_by")


class AcknowledgmentManagementSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.user.get_full_name", read_only=True)
    material_title = serializers.CharField(source="version.material.title", read_only=True)

    class Meta:
        model = MaterialAcknowledgmentAssignment
        fields = ("id", "employee", "employee_name", "material_title", "version", "status", "due_at", "acknowledged_at", "requires_test")


class AcknowledgmentManagementView(ListAPIView):
    permission_classes = [IsLearningManager]
    serializer_class = AcknowledgmentManagementSerializer

    def get_queryset(self):
        return MaterialAcknowledgmentAssignment.objects.filter(
            company_filter(self.request.user, "employee__company_id")
        ).select_related("employee__user", "version__material")


class KnowledgeAnalyticsSerializer(serializers.Serializer):
    total_materials = serializers.IntegerField()
    popular = serializers.ListField()
    rarely_used = serializers.ListField()
    without_owner = serializers.IntegerField()
    needs_update = serializers.IntegerField()
    pending_acknowledgments = serializers.IntegerField()
    new_versions = serializers.IntegerField()
    popular_ttk = serializers.ListField()


class KnowledgeAnalyticsView(GenericAPIView):
    permission_classes = [IsLearningManager]
    serializer_class = KnowledgeAnalyticsSerializer

    def get(self, request):
        materials = KnowledgeMaterial.objects.filter(company_filter(request.user, "owner_department__company_id"))
        ranked = materials.annotate(views_count=Count("views")).order_by("-views_count")
        since = timezone.now() - timedelta(days=30)
        data = {
            "total_materials": materials.count(),
            "popular": list(ranked.values("id", "title", "views_count")[:10]),
            "rarely_used": list(ranked.order_by("views_count").values("id", "title", "views_count")[:10]),
            "without_owner": materials.filter(owner__isnull=True).count(),
            "needs_update": materials.filter(Q(status=KnowledgeMaterial.Status.NEEDS_UPDATE) | Q(review_at__lt=timezone.now())).count(),
            "pending_acknowledgments": MaterialAcknowledgmentAssignment.objects.filter(company_filter(request.user, "employee__company_id")).exclude(status__in=[MaterialAcknowledgmentAssignment.Status.ACKNOWLEDGED, MaterialAcknowledgmentAssignment.Status.CANCELLED]).count(),
            "new_versions": materials.filter(versions__created_at__gte=since).values("versions__id").distinct().count(),
            "popular_ttk": list(ranked.filter(material_type=KnowledgeMaterial.Type.TTK).values("id", "title", "views_count")[:10]),
        }
        return Response(self.get_serializer(data).data)
