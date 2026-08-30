from rest_framework import serializers

from service_requests.models import RequestType, Service
from organizations.models import LegalEntity, Location, OrgUnit
from .models import (BusinessCalendar, BusinessCalendarException,
                     BusinessCalendarExceptionInterval,
                     BusinessCalendarVersion,
                     BusinessCalendarWorkingInterval, SLAPolicy,
                     SLAPolicyAssignmentRule, SLAPolicyVersion,
                     SLAWarningThreshold, TimeMode, SLAInstance,
                     SLAMetricInstance, SLAResolutionCycle, SLAPausePeriod,
                     SLAThresholdEvent)
from .models import (EscalationPolicy,EscalationRule,EscalationActionDefinition,
                     EscalationPolicyVersion,SLAEscalationBinding,
                     EscalationInstance,EscalationExecution,EscalationSchedule)


class WorkingIntervalSerializer(serializers.ModelSerializer):
    class Meta:model=BusinessCalendarWorkingInterval;fields="__all__";read_only_fields=("id","calendar","created_at","updated_at")
class ExceptionIntervalSerializer(serializers.ModelSerializer):
    class Meta:model=BusinessCalendarExceptionInterval;fields=("id","start_time","end_time","position");read_only_fields=("id",)
class CalendarExceptionSerializer(serializers.ModelSerializer):
    intervals=ExceptionIntervalSerializer(many=True,required=False)
    class Meta:model=BusinessCalendarException;fields=("id","calendar","date","exception_type","name","created_at","created_by","intervals");read_only_fields=("id","calendar","created_at","created_by")
class CalendarVersionSerializer(serializers.ModelSerializer):
    class Meta:model=BusinessCalendarVersion;fields="__all__";read_only_fields=fields
class BusinessCalendarSerializer(serializers.ModelSerializer):
    current_version_number=serializers.IntegerField(source="current_version.version",read_only=True)
    class Meta:model=BusinessCalendar;fields="__all__";read_only_fields=("id","created_by","current_version","created_at","updated_at")
class WarningThresholdSerializer(serializers.ModelSerializer):
    class Meta:model=SLAWarningThreshold;fields="__all__";read_only_fields=fields
class PolicyVersionSerializer(serializers.ModelSerializer):
    warning_thresholds=WarningThresholdSerializer(many=True,read_only=True)
    class Meta:model=SLAPolicyVersion;fields="__all__";read_only_fields=fields
class SLAPolicySerializer(serializers.ModelSerializer):
    current_version_number=serializers.IntegerField(source="current_version.version",read_only=True)
    class Meta:model=SLAPolicy;fields="__all__";read_only_fields=("id","created_by","current_version","created_at","updated_at")
class AssignmentRuleSerializer(serializers.ModelSerializer):
    class Meta:model=SLAPolicyAssignmentRule;fields="__all__";read_only_fields=("id","created_at","updated_at")
class PolicyPublishSerializer(serializers.Serializer):
    effective_from=serializers.DateTimeField(required=False,allow_null=True)
    effective_to=serializers.DateTimeField(required=False,allow_null=True)

    def validate(self,data):
        if data.get("effective_from") and data.get("effective_to") and data["effective_from"]>=data["effective_to"]:raise serializers.ValidationError("effective_to must be after effective_from.")
        return data
class PolicyPreviewSerializer(serializers.Serializer):
    request_type=serializers.PrimaryKeyRelatedField(queryset=RequestType.objects.all(),required=False,allow_null=True);service=serializers.PrimaryKeyRelatedField(queryset=Service.objects.all(),required=False,allow_null=True);priority=serializers.ChoiceField(choices=["low","normal","high","critical"],required=False,default="normal")
    legal_entity=serializers.PrimaryKeyRelatedField(queryset=LegalEntity.objects.all(),required=False,allow_null=True);org_unit=serializers.PrimaryKeyRelatedField(queryset=OrgUnit.objects.all(),required=False,allow_null=True);location=serializers.PrimaryKeyRelatedField(queryset=Location.objects.all(),required=False,allow_null=True);at=serializers.DateTimeField(required=False)
class DeadlinePreviewSerializer(serializers.Serializer):
    calendar=serializers.PrimaryKeyRelatedField(queryset=BusinessCalendar.objects.all(),required=False,allow_null=True);time_mode=serializers.ChoiceField(choices=TimeMode.choices);start_at=serializers.DateTimeField();duration_seconds=serializers.IntegerField(min_value=0)
    def validate(self,data):
        if data["time_mode"]==TimeMode.BUSINESS_TIME and not data.get("calendar"):raise serializers.ValidationError("Calendar is required for business time.")
        return data

class RuntimeMetricSerializer(serializers.ModelSerializer):
    cycle=serializers.IntegerField(source="resolution_cycle.cycle_number",read_only=True,allow_null=True)
    class Meta:model=SLAMetricInstance;fields=("id","metric_type","status","duration_seconds","started_at","due_at","achieved_at","breached_at","last_evaluated_at","cycle")
class ResolutionCycleSerializer(serializers.ModelSerializer):
    metric=RuntimeMetricSerializer(read_only=True);pauses=serializers.SerializerMethodField()
    class Meta:model=SLAResolutionCycle;fields=("id","cycle_number","started_at","due_at","achieved_at","breached_at","metric","pauses")
    def get_pauses(self,obj):return [{"reason":p.reason,"started_at":p.started_at,"ended_at":p.ended_at,"elapsed_seconds":p.elapsed_seconds,"business_seconds":p.business_seconds} for p in obj.pause_periods.all()]
class SLAInstanceSerializer(serializers.ModelSerializer):
    policy=serializers.SerializerMethodField();response=serializers.SerializerMethodField();resolution=serializers.SerializerMethodField()
    class Meta:model=SLAInstance;fields=("id","status","started_at","policy","response","resolution","created_at","updated_at")
    def get_policy(self,obj):return {"id":str(obj.policy_version.policy_id),"name":obj.policy_version.policy.name,"version":obj.policy_version.version}
    def get_response(self,obj):
        metric=next((m for m in obj.metrics.all() if m.metric_type=="response"),None);return RuntimeMetricSerializer(metric).data if metric else None
    def get_resolution(self,obj):
        metric=next((m for m in reversed(list(obj.metrics.all())) if m.metric_type=="resolution"),None);return RuntimeMetricSerializer(metric).data if metric else None

class EscalationActionSerializer(serializers.ModelSerializer):
    class Meta:model=EscalationActionDefinition;fields="__all__";read_only_fields=("id","rule","created_at","updated_at")
class EscalationRuleSerializer(serializers.ModelSerializer):
    actions=EscalationActionSerializer(many=True,read_only=True)
    class Meta:model=EscalationRule;fields="__all__";read_only_fields=("id","policy","created_at","updated_at")
class EscalationPolicySerializer(serializers.ModelSerializer):
    rules=EscalationRuleSerializer(source="draft_rules",many=True,read_only=True);current_version_number=serializers.IntegerField(source="current_version.version",read_only=True)
    class Meta:model=EscalationPolicy;fields="__all__";read_only_fields=("id","created_by","current_version","created_at","updated_at")
class EscalationPolicyVersionSerializer(serializers.ModelSerializer):
    class Meta:model=EscalationPolicyVersion;fields="__all__";read_only_fields=fields
class EscalationBindingSerializer(serializers.ModelSerializer):
    class Meta:model=SLAEscalationBinding;fields="__all__";read_only_fields=("id","created_by","created_at","updated_at")
    def validate(self,data):
        sla_version=data.get("sla_policy_version",getattr(self.instance,"sla_policy_version",None));escalation_version=data.get("escalation_policy_version",getattr(self.instance,"escalation_policy_version",None))
        if sla_version and escalation_version:
            for rule in escalation_version.rules_snapshot:
                if rule["trigger_type"]=="on_warning" and not sla_version.warning_thresholds.filter(metric_type=rule["metric_type"],threshold_percent=rule["threshold_percent"]).exists():raise serializers.ValidationError("Warning rule has no matching immutable SLA threshold.")
        return data
class EscalationExecutionSerializer(serializers.ModelSerializer):
    metric_type=serializers.CharField(source="metric_instance.metric_type",read_only=True);cycle=serializers.IntegerField(source="resolution_cycle.cycle_number",read_only=True,allow_null=True)
    class Meta:model=EscalationExecution;fields=("id","trigger_type","triggered_at","action_type","status","target_snapshot","result_metadata","completed_at","error_code","metric_type","cycle","rule_snapshot")
class EscalationInstanceSerializer(serializers.ModelSerializer):
    policy=serializers.SerializerMethodField();current_level=serializers.SerializerMethodField();executions=EscalationExecutionSerializer(many=True,read_only=True)
    class Meta:model=EscalationInstance;fields=("id","status","policy","current_level","executions","created_at","updated_at")
    def get_policy(self,obj):return {"id":str(obj.policy_version.policy_id),"name":obj.policy_version.policy.name,"version":obj.policy_version.version}
    def get_current_level(self,obj):return max((x.rule_snapshot.get("level",0) for x in obj.executions.all() if x.status in {"succeeded","skipped"}),default=0)
