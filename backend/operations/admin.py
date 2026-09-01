from django.contrib import admin

from .models import WorkerHeartbeat


@admin.register(WorkerHeartbeat)
class WorkerHeartbeatAdmin(admin.ModelAdmin):
    list_display = ("worker_name", "instance_id", "last_seen_at", "last_success_at", "last_error_code", "items_processed")
    readonly_fields = tuple(field.name for field in WorkerHeartbeat._meta.fields)
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
