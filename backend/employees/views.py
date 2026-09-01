from datetime import timedelta
from django.db.models import Q
from django.utils import timezone
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Employee
from .permissions import IsOrganizationManager
from .serializers import EmployeeSerializer
from tasks.models import Task
from tasks.serializers import TaskListSerializer

class EmployeeListView(ListAPIView):
    serializer_class = EmployeeSerializer
    permission_classes = [IsOrganizationManager]
    def get_queryset(self):
        user = self.request.user
        qs = Employee.objects.select_related("user", "department", "company", "manager__user").prefetch_related("facilities")
        if user.is_superuser: return qs
        company_ids = list(user.role_assignments.values_list("company_id", flat=True))
        if hasattr(user, "employee"): company_ids.append(user.employee.company_id)
        return qs.filter(company_id__in=company_ids).distinct()

class EmployeeDetailView(RetrieveAPIView):
    serializer_class = EmployeeSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        qs = Employee.objects.select_related("user", "department", "company", "manager__user").prefetch_related("facilities")
        if self.request.user.is_superuser or self.request.user.role_assignments.filter(role__code__in={"manager", "hr", "admin", "executive", "owner"}).exists(): return qs
        return qs.filter(user=self.request.user)

class PersonalDashboardView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        user = request.user
        active = Task.objects.filter(Q(assignee=user) | Q(collaborators=user)).distinct().exclude(status__in=[Task.Status.CLOSED, Task.Status.COMPLETED, Task.Status.CANCELLED])
        now = timezone.now()
        local_now = timezone.localtime(now)
        day_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        today = active.filter(deadline__lt=day_end).select_related("assignee", "creator", "facility")[:8]
        review = Task.objects.filter(creator=user, status=Task.Status.REVIEW)
        counts = {
            "active": active.count(),
            "today": active.filter(deadline__gte=day_start, deadline__lt=day_end).count(),
            "overdue": active.filter(deadline__lt=now).count(),
            "high_priority": active.filter(priority__in=[Task.Priority.HIGH, Task.Priority.CRITICAL]).count(),
            "on_review": review.count(),
        }
        by_status = [{"status": code, "label": label, "count": active.filter(status=code).count()} for code, label in Task.Status.choices if active.filter(status=code).exists()]
        facilities = []
        if hasattr(user, "employee"):
            facilities = [{"id": f.id, "name": f.name, "address": f.address, "status": f.status} for f in user.employee.facilities.all()]
        return Response({"counts": counts, "today_tasks": TaskListSerializer(today, many=True).data, "by_status": by_status, "facilities": facilities})
