from rest_framework import serializers

from employees.models import Employee
from .models import ChecklistTemplate, ChecklistTemplateItem, TaskAttachment, TaskChecklist, TaskChecklistItem, TaskComment, TaskWatcher


class CommentSerializer(serializers.ModelSerializer):
    mentions = serializers.SerializerMethodField()
    body = serializers.SerializerMethodField()
    author_display = serializers.CharField(source="author.display_name", read_only=True, allow_null=True)

    class Meta:
        model = TaskComment
        fields = ("id", "author", "author_display", "body", "is_internal", "mentions", "created_at", "updated_at", "edited_at", "deleted_at", "deleted_by")
        read_only_fields = fields

    def get_body(self, obj):
        return "Комментарий удалён" if obj.deleted_at else obj.body

    def get_mentions(self, obj):
        return [str(value) for value in obj.mention_records.values_list("employee_id", flat=True)]


class CommentWriteSerializer(serializers.Serializer):
    body = serializers.CharField()
    mentions = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all(), many=True, required=False)
    is_internal = serializers.BooleanField(required=False, default=False)


class AttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskAttachment
        fields = ("id", "original_filename", "content_type", "size", "checksum", "uploaded_by", "created_at", "deleted_at", "deleted_by")
        read_only_fields = fields


class WatcherSerializer(serializers.ModelSerializer):
    employee_display = serializers.CharField(source="employee.display_name", read_only=True)
    class Meta:
        model = TaskWatcher
        fields = ("id", "employee", "employee_display", "added_by", "created_at", "removed_at", "removed_by")
        read_only_fields = fields


class ChecklistItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskChecklistItem
        fields = "__all__"
        read_only_fields = ("id", "checklist", "is_completed", "completed_by", "completed_at", "created_at", "updated_at")


class TaskChecklistSerializer(serializers.ModelSerializer):
    items = ChecklistItemSerializer(many=True, read_only=True)

    class Meta:
        model = TaskChecklist
        fields = "__all__"
        read_only_fields = ("id", "task", "source_template", "created_by", "created_at", "removed_at", "removed_by")


class ChecklistTemplateItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChecklistTemplateItem
        fields = ("id", "text", "position", "required", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class ChecklistTemplateSerializer(serializers.ModelSerializer):
    items = ChecklistTemplateItemSerializer(many=True, required=False)

    class Meta:
        model = ChecklistTemplate
        fields = ("id", "name", "description", "is_active", "created_by", "created_at", "updated_at", "items")
        read_only_fields = ("id", "created_by", "created_at", "updated_at")


class ManualChecklistSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    items = ChecklistTemplateItemSerializer(many=True, required=False)


class TemplateApplySerializer(serializers.Serializer):
    template = serializers.PrimaryKeyRelatedField(queryset=ChecklistTemplate.objects.filter(is_active=True))


class WatcherWriteSerializer(serializers.Serializer):
    employee = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all())
