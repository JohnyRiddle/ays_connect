from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied
from employees.models import Employee
from .services import company_dashboard,employee_metrics
class MyPerformanceView(APIView):
    def get(self,request):
        if not hasattr(request.user,"employee"):raise PermissionDenied("Нет карточки сотрудника")
        return Response(employee_metrics(request.user.employee))
class ManagementDashboardView(APIView):
    def get(self,request):
        roles=request.user.role_assignments.filter(role__code__in={"manager","facility_manager","admin","executive","owner","hr"})
        if not request.user.is_superuser and not roles.exists():raise PermissionDenied("Доступно руководителю")
        company=request.user.employee.company if hasattr(request.user,"employee") else roles.first().company
        return Response(company_dashboard(company))
