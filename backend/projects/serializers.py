from rest_framework import serializers
from work_tasks.models import Task

from .models import Project, ProjectAttachment, ProjectComment, ProjectMember, ProjectMilestone, ProjectStage


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        unexpected=set(data)-set(self.fields)
        if unexpected:
            raise serializers.ValidationError({"code":"project_unknown_fields","detail":"Недопустимые поля запроса."})
        return super().to_internal_value(data)


class ProjectSerializer(serializers.ModelSerializer):
    manager_name = serializers.CharField(source="manager.display_name", read_only=True, allow_null=True)

    class Meta:
        model = Project
        fields = ("id", "number", "name", "description", "goal", "expected_result", "manager", "manager_name",
                  "customer", "org_unit", "location", "planned_start_at", "planned_end_at", "actual_start_at",
                  "actual_end_at", "status", "is_archived", "version", "created_by", "updated_by", "created_at", "updated_at")
        read_only_fields = ("id", "number", "manager_name", "actual_start_at", "actual_end_at", "status",
                            "is_archived", "version", "created_by", "updated_by", "created_at", "updated_at")


class StageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectStage
        fields = ("id", "project", "name", "description", "position", "planned_start_at", "planned_end_at", "responsible", "created_at", "updated_at")
        read_only_fields = ("id", "project", "created_at", "updated_at")


class MemberSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.display_name", read_only=True)

    class Meta:
        model = ProjectMember
        fields = ("id", "project", "employee", "employee_name", "role", "joined_at", "left_at")
        read_only_fields = ("id", "project", "employee_name", "joined_at", "left_at")


class MilestoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectMilestone
        fields = ("id", "project", "stage", "name", "due_at", "criterion", "required", "responsible",
                  "confirmed_at", "confirmed_by", "confirmation_comment", "created_at", "updated_at")
        read_only_fields = ("id", "project", "confirmed_at", "confirmed_by", "confirmation_comment", "created_at", "updated_at")


class VersionSerializer(StrictSerializer):
    version = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(required=False, allow_blank=True)


class ProjectEditSerializer(serializers.ModelSerializer):
    version = serializers.IntegerField(min_value=1)

    class Meta:
        model = Project
        fields = ("version", "name", "description", "goal", "expected_result", "manager", "customer",
                  "org_unit", "location", "planned_start_at", "planned_end_at")
        extra_kwargs = {field: {"required": False} for field in ("name", "description", "goal", "expected_result",
                        "manager", "customer", "org_unit", "location", "planned_start_at", "planned_end_at")}


class MemberWriteSerializer(StrictSerializer):
    version = serializers.IntegerField(min_value=1)
    employee = serializers.UUIDField()
    role = serializers.ChoiceField(choices=ProjectMember.Role.choices, default=ProjectMember.Role.MEMBER)


class StageWriteSerializer(StrictSerializer):
    version = serializers.IntegerField(min_value=1)
    name = serializers.CharField(max_length=240)
    description = serializers.CharField(required=False, allow_blank=True)
    position = serializers.IntegerField(min_value=1, default=1)
    planned_start_at = serializers.DateTimeField(required=False, allow_null=True)
    planned_end_at = serializers.DateTimeField(required=False, allow_null=True)
    responsible = serializers.UUIDField(required=False, allow_null=True)


class MilestoneWriteSerializer(StrictSerializer):
    version = serializers.IntegerField(min_value=1)
    name = serializers.CharField(max_length=240)
    stage = serializers.UUIDField(required=False, allow_null=True)
    due_at = serializers.DateTimeField(required=False, allow_null=True)
    criterion = serializers.CharField(required=False, allow_blank=True)
    required = serializers.BooleanField(default=False)
    responsible = serializers.UUIDField(required=False, allow_null=True)


class StageEditSerializer(StageWriteSerializer):
    name = serializers.CharField(max_length=240, required=False)
    position = serializers.IntegerField(min_value=1, required=False)


class MilestoneEditSerializer(MilestoneWriteSerializer):
    name = serializers.CharField(max_length=240, required=False)
    required = serializers.BooleanField(required=False)


class MilestoneActionSerializer(StrictSerializer):
    project_version = serializers.IntegerField(min_value=1)
    comment = serializers.CharField(required=False, allow_blank=True)


class LinkSerializer(StrictSerializer):
    project_version = serializers.IntegerField(min_value=1)
    task_version = serializers.IntegerField(min_value=1)
    task = serializers.UUIDField()
    stage = serializers.UUIDField(required=False, allow_null=True)


class UnlinkSerializer(StrictSerializer):
    project_version = serializers.IntegerField(min_value=1)
    task_version = serializers.IntegerField(min_value=1)
    task = serializers.UUIDField()
    reason = serializers.CharField(required=False, allow_blank=True)


class MoveStageSerializer(UnlinkSerializer):
    stage = serializers.UUIDField(required=False, allow_null=True)


class MoveProjectSerializer(StrictSerializer):
    source_version = serializers.IntegerField(min_value=1)
    target_version = serializers.IntegerField(min_value=1)
    task_version = serializers.IntegerField(min_value=1)
    task = serializers.UUIDField()
    target_project = serializers.UUIDField()
    target_stage = serializers.UUIDField(required=False, allow_null=True)
    reason = serializers.CharField(required=False, allow_blank=True)


class ProjectTaskCreateSerializer(StrictSerializer):
    project_version = serializers.IntegerField(min_value=1)
    stage = serializers.UUIDField(required=False, allow_null=True)
    template = serializers.UUIDField(required=False)
    title = serializers.CharField(max_length=240, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    priority = serializers.ChoiceField(choices=Task._meta.get_field("priority").choices, required=False)
    planned_start_at = serializers.DateTimeField(required=False, allow_null=True)
    responsible_target = serializers.UUIDField(required=False, allow_null=True)
    executor_target = serializers.UUIDField(required=False, allow_null=True)
    due_at = serializers.DateTimeField(required=False, allow_null=True)
    acceptance_policy = serializers.ChoiceField(choices=Task._meta.get_field("acceptance_policy").choices, required=False)


class ProjectCommentSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.display_name",read_only=True)
    body = serializers.SerializerMethodField()
    mentions = serializers.SerializerMethodField()

    class Meta:
        model=ProjectComment
        fields=("id","author","author_name","body","mentions","created_at","updated_at","deleted_at")
        read_only_fields=fields

    def get_body(self,obj):
        return "Комментарий удалён" if obj.deleted_at else obj.body

    def get_mentions(self,obj):
        return [str(value) for value in obj.mentions.values_list("employee_id",flat=True)]


class ProjectCommentWriteSerializer(StrictSerializer):
    body=serializers.CharField()
    mentions=serializers.ListField(child=serializers.UUIDField(),required=False,default=list)


class ProjectAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model=ProjectAttachment
        fields=("id","original_filename","content_type","size","checksum","uploaded_by","created_at","deleted_at")
        read_only_fields=fields
