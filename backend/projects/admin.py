from django.contrib import admin

from .models import (Project, ProjectAttachment, ProjectComment, ProjectCommentMention,
                     ProjectMember, ProjectMilestone, ProjectMilestoneDueNotice, ProjectMilestoneHistory, ProjectStage,
                     ProjectTaskLink, ProjectTaskLinkHistory)


class ProjectReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Project)
class ProjectAdmin(ProjectReadOnlyAdmin):
    list_display = ("number", "name", "status", "manager", "planned_end_at", "is_archived")
    list_filter = ("status", "is_archived", "org_unit")
    search_fields = ("number", "name")


for model in (ProjectMember, ProjectStage, ProjectMilestone, ProjectMilestoneDueNotice, ProjectMilestoneHistory,
              ProjectTaskLink, ProjectTaskLinkHistory, ProjectComment, ProjectCommentMention,
              ProjectAttachment):
    admin.site.register(model, ProjectReadOnlyAdmin)
