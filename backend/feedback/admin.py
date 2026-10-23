from django.contrib import admin
from .models import Feedback
from .permissions import is_owner


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("id", "kind", "created_at", "delivery_status")
    readonly_fields = tuple(field.name for field in Feedback._meta.fields)
    actions = None

    def has_module_permission(self, request):
        return is_owner(request.user)

    def has_view_permission(self, request, obj=None):
        return is_owner(request.user)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs if is_owner(request.user) else qs.none()
