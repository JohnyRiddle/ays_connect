from django.contrib import admin

from .models import ChecklistTemplate, ChecklistTemplateItem, Task, TaskAssignmentHistory, TaskAttachment, TaskChecklist, TaskChecklistItem, TaskComment, TaskDeadlineHistory, TaskOccurrence, TaskRecurrenceRule, TaskReviewHistory, TaskSavedView, TaskStatusHistory, TaskTemplate, TaskTemplateChecklist, TaskWaitingPeriod, TaskWatcher


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "status", "priority", "author", "responsible_employee", "executor_employee", "due_at", "created_at")
    list_filter = ("status", "priority", "legal_entity", "org_unit")
    search_fields = ("number", "title")
    readonly_fields = ("number", "status", "responsible_target", "responsible_employee", "executor_target", "executor_employee", "due_at", "initial_due_at", "started_at", "completed_at", "cancelled_at", "waiting_reason", "waiting_comment", "expected_resume_at", "cancellation_reason", "completion_comment", "parent", "version", "created_by", "updated_by", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


for model in (TaskStatusHistory, TaskWaitingPeriod, TaskDeadlineHistory, TaskAssignmentHistory, TaskReviewHistory):
    admin.site.register(model)


class HistoricalAdmin(admin.ModelAdmin):
    readonly_fields = ()
    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields) if obj else self.readonly_fields
    def has_delete_permission(self, request, obj=None): return False
    def has_add_permission(self, request): return False


@admin.register(TaskComment)
class TaskCommentAdmin(HistoricalAdmin):
    list_display = ("task", "author", "is_internal", "created_at", "deleted_at")
    readonly_fields = ("author", "created_at", "updated_at", "edited_at", "deleted_at", "deleted_by")


@admin.register(TaskAttachment)
class TaskAttachmentAdmin(HistoricalAdmin):
    list_display = ("task", "original_filename", "content_type", "size", "uploaded_by", "created_at", "deleted_at")
    readonly_fields = ("file", "original_filename", "content_type", "size", "checksum", "uploaded_by", "created_at", "deleted_at", "deleted_by")


@admin.register(TaskWatcher)
class TaskWatcherAdmin(HistoricalAdmin):
    list_display = ("task", "employee", "added_by", "created_at", "removed_at")
    readonly_fields = ("added_by", "created_at", "removed_at", "removed_by")


admin.site.register(ChecklistTemplate)
admin.site.register(ChecklistTemplateItem)
admin.site.register(TaskChecklist)


@admin.register(TaskChecklistItem)
class TaskChecklistItemAdmin(HistoricalAdmin):
    list_display = ("checklist", "text", "required", "is_completed", "completed_by", "completed_at")
    readonly_fields = ("completed_by", "completed_at", "created_at", "updated_at")


@admin.register(TaskTemplate)
class TaskTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "default_priority", "legal_entity", "org_unit", "is_active", "updated_at")
    list_filter = ("is_active", "default_priority", "legal_entity", "org_unit")
    search_fields = ("name", "task_title")
    readonly_fields = ("created_by", "created_at", "updated_at")
    def has_delete_permission(self, request, obj=None): return False


admin.site.register(TaskTemplateChecklist)


@admin.register(TaskRecurrenceRule)
class TaskRecurrenceRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "task_template", "timezone", "is_active", "next_occurrence_at", "last_generated_at")
    list_filter = ("is_active", "timezone")
    readonly_fields = ("created_by", "last_generated_at", "last_error", "created_at", "updated_at")
    def has_delete_permission(self, request, obj=None): return False


@admin.register(TaskOccurrence)
class TaskOccurrenceAdmin(HistoricalAdmin):
    list_display = ("recurrence_rule", "occurrence_at", "status", "task", "attempts", "processed_at")
    list_filter = ("status",)


@admin.register(TaskSavedView)
class TaskSavedViewAdmin(HistoricalAdmin):
    list_display = ("owner", "name", "is_default", "is_active", "updated_at")
