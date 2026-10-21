from django.conf import settings
from employees.assignment_targets import assignable_employees
from rest_framework.permissions import BasePermission
from uuid import UUID

OWNER_EMAIL = "ivan@ays-connect.ru"


def owner_employee():
    # Pin both immutable identities; email or a superuser role alone is not identity.
    user_id = settings.FEEDBACK_OWNER_USER_ID
    employee_id = settings.FEEDBACK_OWNER_EMPLOYEE_ID
    if not user_id or not employee_id:
        return None
    try:
        user_id, employee_id = int(user_id), UUID(str(employee_id))
    except (ValueError, TypeError, AttributeError):
        return None
    return assignable_employees().filter(
        pk=employee_id, user_id=user_id, user__email=OWNER_EMAIL,
        user__is_active=True, account_access_state="normal",
    ).select_related("user").first()


def is_owner(user):
    if not user or not user.is_authenticated or not user.is_active:
        return False
    owner = owner_employee()
    return bool(owner and owner.user_id == user.pk)


class ActiveFeedbackUser(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user.is_authenticated and user.is_active and
                    assignable_employees().filter(user=user, account_access_state="normal").exists())


class OwnerOnly(BasePermission):
    def has_permission(self, request, view):
        return is_owner(request.user)

    def has_object_permission(self, request, view, obj):
        return is_owner(request.user)
