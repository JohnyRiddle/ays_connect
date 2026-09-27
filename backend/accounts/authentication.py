from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from .revocation import require_current_credentials


class ActiveEmployeeJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        require_current_credentials(user, validated_token)
        employee = getattr(user, "employee", None)
        if employee and (not employee.is_active or employee.status in {"archived", "suspended", "dismissed", "terminated"}):
            raise AuthenticationFailed("Account is unavailable.", code="account_unavailable")
        return user
