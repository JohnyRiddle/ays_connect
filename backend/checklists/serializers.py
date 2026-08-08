from rest_framework import serializers
from .models import ChecklistAnswer, ChecklistQuestion, ChecklistRun, ChecklistTemplate, Violation

class QuestionSerializer(serializers.ModelSerializer):
    type_label=serializers.CharField(source="get_question_type_display",read_only=True)
    class Meta: model=ChecklistQuestion; fields=("id","text","question_type","type_label","order","is_required","requires_photo","options","min_value","max_value")
class TemplateSerializer(serializers.ModelSerializer):
    questions=QuestionSerializer(many=True,read_only=True); facility_name=serializers.CharField(source="facility.name",read_only=True); frequency_label=serializers.CharField(source="get_frequency_display",read_only=True)
    default_assignee_name=serializers.CharField(source="default_assignee.get_full_name",read_only=True)
    class Meta: model=ChecklistTemplate; fields=("id","name","category","description","version","facility_name","responsible_role","frequency","frequency_label","opens_at","deadline_time","is_mandatory","is_active","is_haccp","default_assignee_name","next_run_at","questions")
class AnswerSerializer(serializers.ModelSerializer):
    question_text=serializers.CharField(source="question.text",read_only=True)
    class Meta: model=ChecklistAnswer; fields=("id","question","question_text","value","comment","attachment_url","answered_at")
class ViolationSerializer(serializers.ModelSerializer):
    question_text=serializers.CharField(source="question.text",read_only=True); task_id=serializers.IntegerField(read_only=True)
    class Meta: model=Violation; fields=("id","question_text","description","severity","task_id","resolved_at","created_at")
class RunSerializer(serializers.ModelSerializer):
    template=TemplateSerializer(read_only=True); assignee_name=serializers.CharField(source="assignee.get_full_name",read_only=True); facility_name=serializers.CharField(source="facility.name",read_only=True); status_label=serializers.CharField(source="get_status_display",read_only=True)
    answers=AnswerSerializer(many=True,read_only=True); violations=ViolationSerializer(many=True,read_only=True)
    class Meta: model=ChecklistRun; fields=("id","template","assignee_name","facility_name","zone_id","due_at","started_at","completed_at","status","status_label","score","is_reinspection","answers","violations")
