from rest_framework import serializers
from accounts.models import User
from .models import DeadlineChangeRequest, RecurrenceRule, Task, TaskAttachment, TaskComment, TaskHistory

class PersonSerializer(serializers.ModelSerializer):
    full_name=serializers.SerializerMethodField()
    class Meta: model=User; fields=("id","full_name")
    def get_full_name(self,obj): return obj.get_full_name() or obj.email

class CommentSerializer(serializers.ModelSerializer):
    author=PersonSerializer(read_only=True)
    class Meta: model=TaskComment; fields=("id","author","text","created_at")

class HistorySerializer(serializers.ModelSerializer):
    actor=PersonSerializer(read_only=True)
    class Meta: model=TaskHistory; fields=("id","actor","action","from_status","to_status","details","created_at")

class AttachmentSerializer(serializers.ModelSerializer):
    uploader=PersonSerializer(read_only=True)
    class Meta: model=TaskAttachment; fields=("id","uploader","original_name","content_type","size","created_at")

class DeadlineRequestSerializer(serializers.ModelSerializer):
    class Meta: model=DeadlineChangeRequest; fields=("id","current_deadline","proposed_deadline","reason_type","reason","status","created_at"); read_only_fields=("current_deadline","status","created_at")

class TaskListSerializer(serializers.ModelSerializer):
    assignee=PersonSerializer(read_only=True); creator=PersonSerializer(read_only=True)
    facility_name=serializers.CharField(source="facility.name",read_only=True)
    status_label=serializers.CharField(source="get_status_display",read_only=True)
    priority_label=serializers.CharField(source="get_priority_display",read_only=True)
    is_overdue=serializers.BooleanField(read_only=True)
    class Meta: model=Task; fields=("id","title","assignee","creator","facility_name","category","priority","priority_label","status","status_label","deadline","is_overdue","source","updated_at")

class TaskDetailSerializer(TaskListSerializer):
    comments=CommentSerializer(many=True,read_only=True); history=HistorySerializer(many=True,read_only=True)
    attachments=AttachmentSerializer(many=True,read_only=True)
    recurrence=serializers.SerializerMethodField()
    collaborators=PersonSerializer(many=True,read_only=True); observers=PersonSerializer(many=True,read_only=True); approvers=PersonSerializer(many=True,read_only=True)
    subtasks=TaskListSerializer(many=True,read_only=True)
    def get_recurrence(self,obj):
        try: rule=obj.recurrence
        except RecurrenceRule.DoesNotExist: return None
        return {"frequency":rule.frequency,"interval":rule.interval,"weekdays":rule.weekdays,"next_run_at":rule.next_run_at,"is_active":rule.is_active}
    class Meta(TaskListSerializer.Meta): fields=TaskListSerializer.Meta.fields+("description","department_id","zone_id","collaborators","observers","approvers","criticality","complexity","estimated_minutes","planned_start","initial_deadline","acceptance_criteria","requires_review","requires_comment","requires_photo","requires_file","result_text","comments","attachments","recurrence","history","subtasks","created_at")

class TaskWriteSerializer(serializers.ModelSerializer):
    class Meta: model=Task; fields=("title","description","assignee","collaborators","observers","approvers","facility","department","zone","parent","category","priority","criticality","complexity","estimated_minutes","planned_start","deadline","acceptance_criteria","requires_review","requires_comment","requires_photo","requires_file","source","status")
    def create(self,validated_data):
        validated_data["creator"]=self.context["request"].user
        validated_data["initial_deadline"]=validated_data["deadline"]
        validated_data["status"]=Task.Status.ASSIGNED
        return super().create(validated_data)

class RecurrenceSerializer(serializers.ModelSerializer):
    class Meta: model=RecurrenceRule; fields=("frequency","interval","weekdays","next_run_at","is_active")
