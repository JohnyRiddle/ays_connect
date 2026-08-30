import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import ValidationError
from django.db import models


class UUIDTimeModel(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    created_at=models.DateTimeField(auto_now_add=True);updated_at=models.DateTimeField(auto_now=True)
    class Meta:abstract=True


class Weekday(models.IntegerChoices):
    MONDAY=0,"Monday";TUESDAY=1,"Tuesday";WEDNESDAY=2,"Wednesday";THURSDAY=3,"Thursday";FRIDAY=4,"Friday";SATURDAY=5,"Saturday";SUNDAY=6,"Sunday"


class BusinessCalendar(UUIDTimeModel):
    name=models.CharField(max_length=200);code=models.CharField(max_length=64,unique=True);timezone=models.CharField(max_length=64);description=models.TextField(blank=True)
    is_default=models.BooleanField(default=False,db_index=True);is_active=models.BooleanField(default=True,db_index=True)
    created_by=models.ForeignKey("employees.Employee",on_delete=models.PROTECT,related_name="created_business_calendars")
    current_version=models.OneToOneField("BusinessCalendarVersion",on_delete=models.PROTECT,null=True,blank=True,related_name="current_for_calendar")
    class Meta:ordering=("name","id");constraints=[models.UniqueConstraint(fields=["is_default"],condition=models.Q(is_default=True),name="one_default_business_calendar")]
    def clean(self):
        try:ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as exc:raise ValidationError({"timezone":"Unknown IANA timezone."}) from exc
    def __str__(self):return self.name


class BusinessCalendarWorkingInterval(UUIDTimeModel):
    calendar=models.ForeignKey(BusinessCalendar,on_delete=models.CASCADE,related_name="working_intervals");weekday=models.PositiveSmallIntegerField(choices=Weekday.choices)
    start_time=models.TimeField();end_time=models.TimeField();position=models.PositiveIntegerField(default=0);is_active=models.BooleanField(default=True,db_index=True)
    class Meta:ordering=("weekday","position","start_time","id");indexes=[models.Index(fields=["calendar","weekday","is_active"])]
    def clean(self):
        if self.start_time>=self.end_time:raise ValidationError("Working interval start must be before end.")


class CalendarExceptionType(models.TextChoices):
    NON_WORKING_DAY="non_working_day","Non-working day";WORKING_DAY="working_day","Working day";CUSTOM_HOURS="custom_hours","Custom hours"


class BusinessCalendarException(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    calendar=models.ForeignKey(BusinessCalendar,on_delete=models.CASCADE,related_name="exceptions");date=models.DateField();exception_type=models.CharField(max_length=24,choices=CalendarExceptionType.choices);name=models.CharField(max_length=200,blank=True)
    created_at=models.DateTimeField(auto_now_add=True);created_by=models.ForeignKey("employees.Employee",on_delete=models.PROTECT,related_name="created_calendar_exceptions")
    class Meta:ordering=("date","id");constraints=[models.UniqueConstraint(fields=["calendar","date"],name="unique_calendar_exception_date")];indexes=[models.Index(fields=["calendar","date"])]


class BusinessCalendarExceptionInterval(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    exception=models.ForeignKey(BusinessCalendarException,on_delete=models.CASCADE,related_name="intervals");start_time=models.TimeField();end_time=models.TimeField();position=models.PositiveIntegerField(default=0)
    class Meta:ordering=("position","start_time","id")
    def clean(self):
        if self.start_time>=self.end_time:raise ValidationError("Exception interval start must be before end.")


class BusinessCalendarVersion(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    calendar=models.ForeignKey(BusinessCalendar,on_delete=models.PROTECT,related_name="versions");version=models.PositiveIntegerField();timezone=models.CharField(max_length=64);schedule_snapshot=models.JSONField();exceptions_snapshot=models.JSONField()
    created_at=models.DateTimeField(auto_now_add=True);created_by=models.ForeignKey("employees.Employee",on_delete=models.PROTECT,related_name="published_calendar_versions")
    class Meta:ordering=("-version",);constraints=[models.UniqueConstraint(fields=["calendar","version"],name="unique_business_calendar_version")]
    def save(self,*args,**kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():raise ValidationError("Published calendar versions are immutable.")
        return super().save(*args,**kwargs)
    def delete(self,*args,**kwargs):raise ValidationError("Published calendar versions are immutable.")


class TimeMode(models.TextChoices):BUSINESS_TIME="business_time","Business time";ELAPSED_TIME="elapsed_time","Elapsed time"
class PausePolicy(models.TextChoices):NONE="none","None";WAITING_REQUESTER="waiting_requester","Waiting requester";WAITING_EXTERNAL="waiting_external","Waiting external";BOTH="waiting_requester_and_external","Requester and external"
class MetricType(models.TextChoices):RESPONSE="response","Response";RESOLUTION="resolution","Resolution"


class SLAPolicy(UUIDTimeModel):
    name=models.CharField(max_length=200);code=models.CharField(max_length=64,unique=True);description=models.TextField(blank=True);is_active=models.BooleanField(default=True,db_index=True)
    draft_time_mode=models.CharField(max_length=20,choices=TimeMode.choices,default=TimeMode.ELAPSED_TIME);draft_calendar=models.ForeignKey(BusinessCalendar,on_delete=models.PROTECT,null=True,blank=True,related_name="draft_sla_policies")
    draft_response_duration_seconds=models.PositiveBigIntegerField(null=True,blank=True);draft_resolution_duration_seconds=models.PositiveBigIntegerField(null=True,blank=True);draft_pause_policy=models.CharField(max_length=40,choices=PausePolicy.choices,default=PausePolicy.NONE);draft_thresholds=models.JSONField(default=list,blank=True)
    created_by=models.ForeignKey("employees.Employee",on_delete=models.PROTECT,related_name="created_sla_policies");current_version=models.OneToOneField("SLAPolicyVersion",on_delete=models.PROTECT,null=True,blank=True,related_name="current_for_policy")
    class Meta:ordering=("name","id")
    def __str__(self):return self.name


class SLAPolicyVersion(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False);policy=models.ForeignKey(SLAPolicy,on_delete=models.PROTECT,related_name="versions");version=models.PositiveIntegerField()
    effective_from=models.DateTimeField(null=True,blank=True);effective_to=models.DateTimeField(null=True,blank=True);time_mode=models.CharField(max_length=20,choices=TimeMode.choices);business_calendar_version=models.ForeignKey(BusinessCalendarVersion,on_delete=models.PROTECT,null=True,blank=True,related_name="sla_policy_versions")
    response_duration_seconds=models.PositiveBigIntegerField(null=True,blank=True);resolution_duration_seconds=models.PositiveBigIntegerField(null=True,blank=True);pause_policy=models.CharField(max_length=40,choices=PausePolicy.choices)
    created_at=models.DateTimeField(auto_now_add=True);created_by=models.ForeignKey("employees.Employee",on_delete=models.PROTECT,related_name="published_sla_policy_versions")
    class Meta:
        ordering=("-version",);constraints=[models.UniqueConstraint(fields=["policy","version"],name="unique_sla_policy_version"),models.CheckConstraint(condition=models.Q(time_mode=TimeMode.ELAPSED_TIME,business_calendar_version__isnull=True)|models.Q(time_mode=TimeMode.BUSINESS_TIME,business_calendar_version__isnull=False),name="sla_policy_version_calendar_mode"),models.CheckConstraint(condition=models.Q(effective_to__isnull=True)|models.Q(effective_from__isnull=True)|models.Q(effective_from__lt=models.F("effective_to")),name="sla_policy_effective_interval")]
    def save(self,*args,**kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():raise ValidationError("Published SLA policy versions are immutable.")
        return super().save(*args,**kwargs)
    def delete(self,*args,**kwargs):raise ValidationError("Published SLA policy versions are immutable.")


class SLAWarningThreshold(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False);policy_version=models.ForeignKey(SLAPolicyVersion,on_delete=models.PROTECT,related_name="warning_thresholds");metric_type=models.CharField(max_length=16,choices=MetricType.choices);threshold_percent=models.PositiveSmallIntegerField();code=models.CharField(max_length=64,blank=True);position=models.PositiveIntegerField(default=0)
    class Meta:ordering=("metric_type","position","threshold_percent");constraints=[models.UniqueConstraint(fields=["policy_version","metric_type","threshold_percent"],name="unique_sla_warning_threshold"),models.CheckConstraint(condition=models.Q(threshold_percent__gt=0,threshold_percent__lte=100),name="sla_warning_threshold_range")]


class SLAPolicyAssignmentRule(UUIDTimeModel):
    policy=models.ForeignKey(SLAPolicy,on_delete=models.PROTECT,related_name="assignment_rules");order=models.PositiveIntegerField(default=100)
    request_type=models.ForeignKey("service_requests.RequestType",on_delete=models.PROTECT,null=True,blank=True,related_name="sla_assignment_rules");service=models.ForeignKey("service_requests.Service",on_delete=models.PROTECT,null=True,blank=True,related_name="sla_assignment_rules");request_priority=models.CharField(max_length=16,choices=[("low","Low"),("normal","Normal"),("high","High"),("critical","Critical")],blank=True)
    legal_entity=models.ForeignKey("organizations.LegalEntity",on_delete=models.PROTECT,null=True,blank=True,related_name="sla_assignment_rules");org_unit=models.ForeignKey("organizations.OrgUnit",on_delete=models.PROTECT,null=True,blank=True,related_name="sla_assignment_rules");location=models.ForeignKey("organizations.Location",on_delete=models.PROTECT,null=True,blank=True,related_name="sla_assignment_rules");is_active=models.BooleanField(default=True,db_index=True)
    class Meta:ordering=("order","id");indexes=[models.Index(fields=["request_type"]),models.Index(fields=["service"]),models.Index(fields=["request_priority"]),models.Index(fields=["legal_entity"]),models.Index(fields=["org_unit"]),models.Index(fields=["location"])]


class SLAInstanceStatus(models.TextChoices):
    ACTIVE="active","Active";PAUSED="paused","Paused";COMPLETED="completed","Completed";CANCELLED="cancelled","Cancelled"


class SLAMetricStatus(models.TextChoices):
    ACTIVE="active","Active";PAUSED="paused","Paused";ACHIEVED="achieved","Achieved";BREACHED="breached","Breached";CANCELLED="cancelled","Cancelled"


class PauseReason(models.TextChoices):
    WAITING_REQUESTER="waiting_requester","Waiting requester";WAITING_EXTERNAL="waiting_external","Waiting external"


class SLAInstance(UUIDTimeModel):
    request=models.OneToOneField("service_requests.ServiceRequest",on_delete=models.PROTECT,related_name="sla_instance")
    policy_version=models.ForeignKey(SLAPolicyVersion,on_delete=models.PROTECT,related_name="runtime_instances")
    calendar_version=models.ForeignKey(BusinessCalendarVersion,on_delete=models.PROTECT,null=True,blank=True,related_name="runtime_instances")
    started_at=models.DateTimeField();status=models.CharField(max_length=16,choices=SLAInstanceStatus.choices,default=SLAInstanceStatus.ACTIVE,db_index=True)
    version=models.PositiveIntegerField(default=1)
    class Meta:indexes=[models.Index(fields=["status","updated_at"])]


class SLAResolutionCycle(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False);sla_instance=models.ForeignKey(SLAInstance,on_delete=models.PROTECT,related_name="resolution_cycles")
    cycle_number=models.PositiveIntegerField();started_at=models.DateTimeField();due_at=models.DateTimeField(null=True,blank=True,db_index=True);achieved_at=models.DateTimeField(null=True,blank=True);breached_at=models.DateTimeField(null=True,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:ordering=("cycle_number",);constraints=[models.UniqueConstraint(fields=["sla_instance","cycle_number"],name="unique_sla_resolution_cycle")]


class SLAMetricInstance(UUIDTimeModel):
    sla_instance=models.ForeignKey(SLAInstance,on_delete=models.PROTECT,related_name="metrics");resolution_cycle=models.OneToOneField(SLAResolutionCycle,on_delete=models.PROTECT,null=True,blank=True,related_name="metric")
    metric_type=models.CharField(max_length=16,choices=MetricType.choices);status=models.CharField(max_length=16,choices=SLAMetricStatus.choices,default=SLAMetricStatus.ACTIVE,db_index=True)
    duration_seconds=models.PositiveBigIntegerField();started_at=models.DateTimeField();due_at=models.DateTimeField(null=True,blank=True,db_index=True);achieved_at=models.DateTimeField(null=True,blank=True);breached_at=models.DateTimeField(null=True,blank=True);last_evaluated_at=models.DateTimeField(null=True,blank=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["sla_instance"],condition=models.Q(metric_type=MetricType.RESPONSE),name="unique_response_metric_per_sla"),models.CheckConstraint(condition=models.Q(metric_type=MetricType.RESPONSE,resolution_cycle__isnull=True)|models.Q(metric_type=MetricType.RESOLUTION,resolution_cycle__isnull=False),name="sla_metric_cycle_kind")]
        indexes=[models.Index(fields=["status","due_at"])]


class SLAPausePeriod(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False);sla_instance=models.ForeignKey(SLAInstance,on_delete=models.PROTECT,related_name="pause_periods");resolution_cycle=models.ForeignKey(SLAResolutionCycle,on_delete=models.PROTECT,related_name="pause_periods")
    reason=models.CharField(max_length=24,choices=PauseReason.choices);started_at=models.DateTimeField();ended_at=models.DateTimeField(null=True,blank=True);business_seconds=models.PositiveBigIntegerField(null=True,blank=True);elapsed_seconds=models.PositiveBigIntegerField(null=True,blank=True);created_at=models.DateTimeField(auto_now_add=True)
    class Meta:ordering=("started_at",);constraints=[models.UniqueConstraint(fields=["sla_instance"],condition=models.Q(ended_at__isnull=True),name="unique_active_sla_pause")];indexes=[models.Index(fields=["sla_instance","ended_at"])]


class SLAThresholdEvent(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False);metric_instance=models.ForeignKey(SLAMetricInstance,on_delete=models.PROTECT,related_name="threshold_events");threshold=models.ForeignKey(SLAWarningThreshold,on_delete=models.PROTECT,related_name="runtime_events");threshold_percent=models.PositiveSmallIntegerField();reached_at=models.DateTimeField();created_at=models.DateTimeField(auto_now_add=True)
    class Meta:ordering=("reached_at","id");constraints=[models.UniqueConstraint(fields=["metric_instance","threshold"],name="unique_sla_metric_threshold_event")]


class EscalationTrigger(models.TextChoices):
    ON_WARNING="on_warning","On warning";ON_BREACH="on_breach","On breach";AFTER_BREACH_DURATION="after_breach_duration","After breach duration"
class EscalationActionType(models.TextChoices):
    REQUEST_NOTIFICATION="request_notification","Request notification";ADD_WATCHER="add_watcher","Add watcher";CHANGE_PRIORITY="change_priority","Change priority";REASSIGN="reassign","Reassign"
class EscalationTargetType(models.TextChoices):
    REQUEST_EXECUTOR="request_executor","Request executor";REQUEST_RESPONSIBLE="request_responsible","Request responsible";REQUEST_REQUESTER="request_requester","Request requester";REQUEST_EXECUTOR_MANAGER="request_executor_manager","Executor manager";REQUEST_RESPONSIBLE_MANAGER="request_responsible_manager","Responsible manager";ASSIGNMENT_TARGET="assignment_target","Assignment target"


class EscalationPolicy(UUIDTimeModel):
    name=models.CharField(max_length=200);code=models.CharField(max_length=64,unique=True);description=models.TextField(blank=True);is_active=models.BooleanField(default=True,db_index=True);created_by=models.ForeignKey("employees.Employee",on_delete=models.PROTECT,related_name="created_escalation_policies");current_version=models.OneToOneField("EscalationPolicyVersion",on_delete=models.PROTECT,null=True,blank=True,related_name="current_for_policy")
    class Meta:ordering=("name","id")


class EscalationRule(UUIDTimeModel):
    policy=models.ForeignKey(EscalationPolicy,on_delete=models.CASCADE,related_name="draft_rules");name=models.CharField(max_length=200);trigger_type=models.CharField(max_length=32,choices=EscalationTrigger.choices);metric_type=models.CharField(max_length=16,choices=MetricType.choices);threshold_percent=models.PositiveSmallIntegerField(null=True,blank=True);delay_seconds=models.PositiveBigIntegerField(null=True,blank=True);level=models.PositiveIntegerField(default=1);position=models.PositiveIntegerField(default=0)
    class Meta:ordering=("level","position","id");constraints=[models.CheckConstraint(condition=models.Q(level__gt=0),name="escalation_rule_positive_level")]


class EscalationActionDefinition(UUIDTimeModel):
    rule=models.ForeignKey(EscalationRule,on_delete=models.CASCADE,related_name="actions");action_type=models.CharField(max_length=32,choices=EscalationActionType.choices);target_type=models.CharField(max_length=40,choices=EscalationTargetType.choices,blank=True);assignment_target=models.ForeignKey("employees.AssignmentTarget",on_delete=models.PROTECT,null=True,blank=True,related_name="escalation_actions");target_config=models.JSONField(default=dict,blank=True);action_config=models.JSONField(default=dict,blank=True);position=models.PositiveIntegerField(default=0)
    class Meta:ordering=("position","id")


class EscalationPolicyVersion(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False);policy=models.ForeignKey(EscalationPolicy,on_delete=models.PROTECT,related_name="versions");version=models.PositiveIntegerField();rules_snapshot=models.JSONField();created_at=models.DateTimeField(auto_now_add=True);created_by=models.ForeignKey("employees.Employee",on_delete=models.PROTECT,related_name="published_escalation_policy_versions")
    class Meta:ordering=("-version",);constraints=[models.UniqueConstraint(fields=["policy","version"],name="unique_escalation_policy_version")]
    def save(self,*args,**kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():raise ValidationError("Published escalation policy versions are immutable.")
        return super().save(*args,**kwargs)
    def delete(self,*args,**kwargs):raise ValidationError("Published escalation policy versions are immutable.")


class SLAEscalationBinding(UUIDTimeModel):
    sla_policy_version=models.ForeignKey(SLAPolicyVersion,on_delete=models.PROTECT,related_name="escalation_bindings");escalation_policy_version=models.ForeignKey(EscalationPolicyVersion,on_delete=models.PROTECT,related_name="sla_bindings");effective_from=models.DateTimeField(null=True,blank=True);is_active=models.BooleanField(default=True,db_index=True);created_by=models.ForeignKey("employees.Employee",on_delete=models.PROTECT,related_name="created_escalation_bindings")
    class Meta:ordering=("-effective_from","-created_at");constraints=[models.UniqueConstraint(fields=["sla_policy_version"],condition=models.Q(is_active=True),name="unique_active_sla_escalation_binding")];indexes=[models.Index(fields=["sla_policy_version","is_active"])]


class EscalationInstanceStatus(models.TextChoices):ACTIVE="active","Active";COMPLETED="completed","Completed";CANCELLED="cancelled","Cancelled"
class EscalationExecutionStatus(models.TextChoices):PENDING="pending","Pending";RUNNING="running","Running";SUCCEEDED="succeeded","Succeeded";SKIPPED="skipped","Skipped";FAILED="failed","Failed"
class EscalationScheduleStatus(models.TextChoices):PENDING="pending","Pending";PROCESSING="processing","Processing";COMPLETED="completed","Completed";CANCELLED="cancelled","Cancelled"


class EscalationInstance(UUIDTimeModel):
    sla_instance=models.OneToOneField(SLAInstance,on_delete=models.PROTECT,related_name="escalation_instance");policy_version=models.ForeignKey(EscalationPolicyVersion,on_delete=models.PROTECT,related_name="runtime_instances");status=models.CharField(max_length=16,choices=EscalationInstanceStatus.choices,default=EscalationInstanceStatus.ACTIVE,db_index=True);version=models.PositiveIntegerField(default=1)
    class Meta:indexes=[models.Index(fields=["status","updated_at"])]


class EscalationSchedule(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False);escalation_instance=models.ForeignKey(EscalationInstance,on_delete=models.PROTECT,related_name="schedules");metric_instance=models.ForeignKey(SLAMetricInstance,on_delete=models.PROTECT,related_name="escalation_schedules");rule_key=models.UUIDField();rule_snapshot=models.JSONField();due_at=models.DateTimeField(db_index=True);status=models.CharField(max_length=16,choices=EscalationScheduleStatus.choices,default=EscalationScheduleStatus.PENDING,db_index=True);created_at=models.DateTimeField(auto_now_add=True);updated_at=models.DateTimeField(auto_now=True)
    class Meta:constraints=[models.UniqueConstraint(fields=["escalation_instance","metric_instance","rule_key"],name="unique_escalation_schedule_context")];indexes=[models.Index(fields=["status","due_at"])]


class EscalationExecution(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False);escalation_instance=models.ForeignKey(EscalationInstance,on_delete=models.PROTECT,related_name="executions");metric_instance=models.ForeignKey(SLAMetricInstance,on_delete=models.PROTECT,related_name="escalation_executions");resolution_cycle=models.ForeignKey(SLAResolutionCycle,on_delete=models.PROTECT,null=True,blank=True,related_name="escalation_executions");rule_key=models.UUIDField();action_key=models.UUIDField();rule_snapshot=models.JSONField();action_snapshot=models.JSONField();trigger_type=models.CharField(max_length=32,choices=EscalationTrigger.choices);triggered_at=models.DateTimeField();due_at=models.DateTimeField(null=True,blank=True);action_type=models.CharField(max_length=32,choices=EscalationActionType.choices);status=models.CharField(max_length=16,choices=EscalationExecutionStatus.choices,default=EscalationExecutionStatus.PENDING,db_index=True);target_snapshot=models.JSONField(default=list,blank=True);result_metadata=models.JSONField(default=dict,blank=True);started_at=models.DateTimeField(null=True,blank=True);completed_at=models.DateTimeField(null=True,blank=True);error_code=models.CharField(max_length=64,blank=True);created_at=models.DateTimeField(auto_now_add=True)
    class Meta:ordering=("triggered_at","created_at");constraints=[models.UniqueConstraint(fields=["escalation_instance","metric_instance","rule_key","action_key"],name="unique_escalation_execution_context")];indexes=[models.Index(fields=["status","triggered_at"])]
    def delete(self,*args,**kwargs):raise ValidationError("Escalation execution history is immutable.")
