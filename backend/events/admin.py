from django.contrib import admin
from .models import OutboxEvent


@admin.register(OutboxEvent)
class OutboxEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "entity_type", "entity_id", "status", "created_at")
    list_filter = ("status", "event_type")
    readonly_fields = tuple(field.name for field in OutboxEvent._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
