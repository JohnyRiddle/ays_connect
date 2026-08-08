from rest_framework import serializers
from .models import Employee

class EmployeeSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    email = serializers.EmailField(source="user.email", read_only=True)
    phone = serializers.CharField(source="user.phone", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True)
    manager_name = serializers.SerializerMethodField()
    facilities = serializers.SerializerMethodField()
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    class Meta:
        model = Employee
        fields = ("id", "full_name", "email", "phone", "employee_number", "position", "department_name", "company_name", "manager_name", "hire_date", "status", "status_label", "work_schedule", "skills", "facilities")
    def get_full_name(self, obj): return obj.user.get_full_name() if obj.user else "Сотрудник без учётной записи"
    def get_manager_name(self, obj): return obj.manager.user.get_full_name() if obj.manager and obj.manager.user else None
    def get_facilities(self, obj): return [{"id": x.id, "name": x.name} for x in obj.facilities.all()]
