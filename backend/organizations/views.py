from rest_framework.generics import ListAPIView
from employees.permissions import IsOrganizationManager
from .models import Company
from .serializers import CompanySerializer

class OrganizationTreeView(ListAPIView):
    serializer_class = CompanySerializer
    permission_classes = [IsOrganizationManager]
    def get_queryset(self):
        user = self.request.user
        qs = Company.objects.prefetch_related("departments", "regions__clusters__facilities__zones")
        if user.is_superuser: return qs
        company_ids = user.role_assignments.values_list("company_id", flat=True)
        if hasattr(user, "employee"): company_ids = list(company_ids) + [user.employee.company_id]
        return qs.filter(id__in=company_ids).distinct()
