from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from rest_framework.exceptions import AuthenticationFailed as DRFAuthenticationFailed
from .models import User

class EmailTokenSerializer(TokenObtainPairSerializer):
    username_field = User.USERNAME_FIELD
    def validate(self, attrs):
        try: data = super().validate(attrs)
        except (AuthenticationFailed, DRFAuthenticationFailed) as exc: raise DRFAuthenticationFailed("Authentication failed.", code="no_active_account") from exc
        employee = getattr(self.user, "employee", None)
        if employee and (not employee.is_active or employee.status in {"archived", "suspended", "dismissed", "terminated"}):
            raise DRFAuthenticationFailed("Authentication failed.", code="no_active_account")
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
        return {"id": e.id, "position": e.position, "department": e.department.name if e.department else None, "company": e.company.name if e.company else None, "employee_number": e.employee_number}


class ActiveTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        refresh = self.token_class(attrs["refresh"])
        try: user = User.objects.select_related("employee").get(pk=refresh["user_id"], is_active=True)
        except User.DoesNotExist as exc: raise AuthenticationFailed("Account is unavailable.", code="account_unavailable") from exc
        employee = getattr(user, "employee", None)
        if employee and (not employee.is_active or employee.status in {"archived", "suspended", "dismissed", "terminated"}):
            raise AuthenticationFailed("Account is unavailable.", code="account_unavailable")
        return super().validate(attrs)
