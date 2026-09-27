from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Role, User, UserRole
@admin.register(User)
class LifecycleUserAdmin(UserAdmin):
    # Lifecycle services own activation and durable credential revocation.
    # A forged form field must not provide an alternate block/restore path.
    readonly_fields = (*UserAdmin.readonly_fields, "is_active", "auth_version")

    def has_delete_permission(self, request, obj=None):
        return False
admin.site.register(Role)
admin.site.register(UserRole)
