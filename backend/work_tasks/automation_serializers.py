from rest_framework import serializers

from .models import ChecklistTemplate, TaskOccurrence, TaskRecurrenceRule, TaskSavedView, TaskTemplate


class TaskTemplateSerializer(serializers.ModelSerializer):
    checklist_templates = serializers.PrimaryKeyRelatedField(queryset=ChecklistTemplate.objects.all(), many=True, required=False)

    class Meta:
        model = TaskTemplate
        fields = "__all__"
        read_only_fields = ("id", "created_by", "created_at", "updated_at", "is_active")


class TemplateCreateTaskSerializer(serializers.Serializer):
    create_and_publish = serializers.BooleanField(default=False)


class RecurrenceSerializer(serializers.ModelSerializer):
    failed_occurrences_count = serializers.SerializerMethodField()

    class Meta:
        model = TaskRecurrenceRule
        fields = "__all__"
        read_only_fields = ("id", "created_by", "is_active", "next_occurrence_at", "last_generated_at", "last_error", "created_at", "updated_at")

    def get_failed_occurrences_count(self, obj):
        annotated = getattr(obj, "failed_occurrences_count_value", None)
        return annotated if annotated is not None else obj.occurrences.filter(status=TaskOccurrence.Status.FAILED).count()


class OccurrenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskOccurrence
        fields = "__all__"
        read_only_fields = tuple(field.name for field in TaskOccurrence._meta.fields)


class OccurrenceSkipSerializer(serializers.Serializer):
    reason = serializers.CharField()


class SavedViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskSavedView
        fields = "__all__"
        read_only_fields = ("id", "owner", "created_at", "updated_at", "is_active")
