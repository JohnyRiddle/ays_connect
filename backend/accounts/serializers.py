from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import User

class EmailTokenSerializer(TokenObtainPairSerializer):
    username_field = User.USERNAME_FIELD
    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = ProfileSerializer(self.user).data
        return data

class ProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    roles = serializers.SerializerMethodField()
    employee = serializers.SerializerMethodField()
    class Meta:
        model = User
        fields = ("id", "email", "phone", "full_name", "roles", "employee", "is_demo")
    def get_full_name(self, obj): return " ".join(filter(None, [obj.last_name, obj.first_name, obj.middle_name]))
    def get_roles(self, obj): return [{"code": x.role.code, "name": x.role.name} for x in obj.role_assignments.select_related("role")]
    def get_employee(self, obj):
        if not hasattr(obj, "employee"): return None
        e = obj.employee
        return {"id": e.id, "position": e.position, "department": e.department.name if e.department else None, "company": e.company.name, "employee_number": e.employee_number}
