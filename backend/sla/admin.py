from django.contrib import admin
from .models import (BusinessCalendar,BusinessCalendarWorkingInterval,BusinessCalendarException,BusinessCalendarExceptionInterval,BusinessCalendarVersion,SLAPolicy,SLAPolicyVersion,SLAWarningThreshold,SLAPolicyAssignmentRule,SLAInstance,SLAMetricInstance,SLAResolutionCycle,SLAPausePeriod,SLAThresholdEvent)
from .models import (EscalationPolicy,EscalationRule,EscalationActionDefinition,EscalationPolicyVersion,SLAEscalationBinding,EscalationInstance,EscalationSchedule,EscalationExecution)

for model in (BusinessCalendar,BusinessCalendarWorkingInterval,BusinessCalendarException,BusinessCalendarExceptionInterval,SLAPolicy,SLAPolicyAssignmentRule):admin.site.register(model)
@admin.register(BusinessCalendarVersion)
class CalendarVersionAdmin(admin.ModelAdmin):
    readonly_fields=("calendar","version","timezone","schedule_snapshot","exceptions_snapshot","created_at","created_by")
    def has_delete_permission(self,request,obj=None):return False
@admin.register(SLAPolicyVersion)
class PolicyVersionAdmin(admin.ModelAdmin):
    readonly_fields=("policy","version","effective_from","effective_to","time_mode","business_calendar_version","response_duration_seconds","resolution_duration_seconds","pause_policy","created_at","created_by")
    def has_delete_permission(self,request,obj=None):return False
@admin.register(SLAWarningThreshold)
class ThresholdAdmin(admin.ModelAdmin):
    readonly_fields=("policy_version","metric_type","threshold_percent","code","position")
    def has_delete_permission(self,request,obj=None):return False

class RuntimeReadOnlyAdmin(admin.ModelAdmin):
    def get_readonly_fields(self,request,obj=None):return tuple(field.name for field in self.model._meta.fields)
    def has_add_permission(self,request):return False
    def has_delete_permission(self,request,obj=None):return False

for runtime_model in (SLAInstance,SLAMetricInstance,SLAResolutionCycle,SLAPausePeriod,SLAThresholdEvent):admin.site.register(runtime_model,RuntimeReadOnlyAdmin)
for configuration_model in (EscalationPolicy,EscalationRule,EscalationActionDefinition,SLAEscalationBinding):admin.site.register(configuration_model)
for readonly_model in (EscalationPolicyVersion,EscalationInstance,EscalationSchedule,EscalationExecution):admin.site.register(readonly_model,RuntimeReadOnlyAdmin)
