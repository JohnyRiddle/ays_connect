from rest_framework import serializers

from .models import Task, TaskAssignmentHistory, TaskChecklistItem, TaskDeadlineHistory, TaskReviewHistory, TaskStatusHistory, TaskWaitingPeriod


class TaskStatusHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskStatusHistory
        fields = "__all__"


class TaskWaitingPeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskWaitingPeriod
        fields = "__all__"


class TaskDeadlineHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskDeadlineHistory
        fields = "__all__"


class TaskAssignmentHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskAssignmentHistory
        fields = "__all__"


class TaskReviewHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskReviewHistory
        fields = "__all__"


class TaskSerializer(serializers.ModelSerializer):
    is_overdue = serializers.BooleanField(read_only=True)
    completed_late = serializers.BooleanField(read_only=True)
    responsible_target_display = serializers.SerializerMethodField()
    executor_target_display = serializers.SerializerMethodField()
    responsible_employee_display = serializers.CharField(source="responsible_employee.display_name", read_only=True, allow_null=True)
    executor_employee_display = serializers.CharField(source="executor_employee.display_name", read_only=True, allow_null=True)
    author_display = serializers.CharField(source="author.display_name", read_only=True, allow_null=True)

    @staticmethod
    def _target_display(target):
        if not target:
            return None
        value = target.employee or target.position or target.org_unit or target.functional_group
        return getattr(value, "display_name", None) or getattr(value, "name", None) or str(value)

    def get_responsible_target_display(self, obj):
        return self._target_display(obj.responsible_target)

    def get_executor_target_display(self, obj):
        return self._target_display(obj.executor_target)

    class Meta:
        model = Task
        fields = "__all__"
        read_only_fields = (
            "id", "number", "status", "author", "responsible_employee", "executor_employee",
            "initial_due_at", "started_at", "completed_at", "cancelled_at", "waiting_reason",
            "waiting_comment", "expected_resume_at", "cancellation_reason", "completion_comment",
            "version", "created_by", "updated_by", "created_at", "updated_at",
        )


class TaskDetailSerializer(TaskSerializer):
    status_history = TaskStatusHistorySerializer(many=True, read_only=True)
    waiting_periods = TaskWaitingPeriodSerializer(many=True, read_only=True)
    deadline_history = TaskDeadlineHistorySerializer(many=True, read_only=True)
    assignment_history = TaskAssignmentHistorySerializer(many=True, read_only=True)
    review_history = TaskReviewHistorySerializer(many=True, read_only=True)
    comments_count = serializers.SerializerMethodField()
    attachments_count = serializers.SerializerMethodField()
    watchers_count = serializers.SerializerMethodField()
    checklists_count = serializers.SerializerMethodField()
    checklist_progress = serializers.SerializerMethodField()
    available_actions = serializers.SerializerMethodField()

    def get_comments_count(self, obj):
        return obj.production_comments.filter(deleted_at__isnull=True).count()

    def get_attachments_count(self, obj):
        return obj.production_attachments.filter(deleted_at__isnull=True).count()

    def get_watchers_count(self, obj):
        return obj.watcher_records.filter(removed_at__isnull=True).count()

    def get_checklists_count(self, obj):
        return obj.production_checklists.filter(removed_at__isnull=True).count()

    def get_checklist_progress(self, obj):
        items = TaskChecklistItem.objects.filter(checklist__task=obj, checklist__removed_at__isnull=True)
        return {"total": items.count(), "completed": items.filter(is_completed=True).count(), "required_incomplete": items.filter(required=True, is_completed=False).count()}

    def get_available_actions(self, obj):
        from .ux import TaskUXService
        request = self.context.get("request")
        if not request or not hasattr(request.user, "employee"):
            return []
        return TaskUXService.available_actions(obj, request.user.employee, request.user.is_superuser)

    class Meta(TaskSerializer.Meta):
        fields = TaskSerializer.Meta.fields


class TaskCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = (
            "title", "description", "responsible_target", "executor_target", "priority",
            "planned_start_at", "due_at", "parent", "org_unit", "legal_entity", "location",
            "completion_policy", "acceptance_policy", "source_type", "source_id",
        )


class TaskPatchSerializer(serializers.Serializer):
    version = serializers.IntegerField(min_value=1)
    title = serializers.CharField(max_length=240, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    priority = serializers.ChoiceField(choices=Task._meta.get_field("priority").choices, required=False)
    planned_start_at = serializers.DateTimeField(required=False, allow_null=True)
    parent = serializers.PrimaryKeyRelatedField(queryset=Task.objects.all(), required=False, allow_null=True)
    org_unit = serializers.PrimaryKeyRelatedField(queryset=Task._meta.get_field("org_unit").remote_field.model.objects.all(), required=False, allow_null=True)
    legal_entity = serializers.PrimaryKeyRelatedField(queryset=Task._meta.get_field("legal_entity").remote_field.model.objects.all(), required=False, allow_null=True)
    location = serializers.PrimaryKeyRelatedField(queryset=Task._meta.get_field("location").remote_field.model.objects.all(), required=False, allow_null=True)
    acceptance_policy = serializers.ChoiceField(choices=Task._meta.get_field("acceptance_policy").choices, required=False)
    completion_policy = serializers.ChoiceField(choices=Task._meta.get_field("completion_policy").choices, required=False)


class VersionSerializer(serializers.Serializer):
    version = serializers.IntegerField(min_value=1)


class PauseSerializer(VersionSerializer):
    reason = serializers.ChoiceField(choices=Task._meta.get_field("waiting_reason").choices)
    comment = serializers.CharField(required=False, allow_blank=True)
    expected_resume_at = serializers.DateTimeField(required=False, allow_null=True)


class ReasonSerializer(VersionSerializer):
    reason = serializers.CharField()


class CompleteSerializer(VersionSerializer):
    completion_comment = serializers.CharField(required=False, allow_blank=True)


class ReviewSerializer(VersionSerializer):
    comment = serializers.CharField(required=False, allow_blank=True)


class DeadlineSerializer(VersionSerializer):
    due_at = serializers.DateTimeField(allow_null=True)
    reason = serializers.CharField(required=False, allow_blank=True)


class ReassignSerializer(VersionSerializer):
    assignment_type = serializers.ChoiceField(choices=TaskAssignmentHistory.Type.choices)
    target = serializers.PrimaryKeyRelatedField(queryset=Task._meta.get_field("responsible_target").remote_field.model.objects.all())
    reason = serializers.CharField(required=False, allow_blank=True)
