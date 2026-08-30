from datetime import timedelta

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from audit.services import AuditService
from events.services import DomainEventService
from .calendars import BusinessTimeCalculator
from .models import (BusinessCalendar, BusinessCalendarException,
                     BusinessCalendarWorkingInterval, SLAPolicy,
                     SLAPolicyAssignmentRule, TimeMode)
from .serializers import (AssignmentRuleSerializer, BusinessCalendarSerializer,
                          CalendarExceptionSerializer, CalendarVersionSerializer,
                          DeadlinePreviewSerializer, PolicyPreviewSerializer,
                          PolicyPublishSerializer, PolicyVersionSerializer, SLAPolicySerializer,
                          WorkingIntervalSerializer)
from .serializers import (EscalationPolicySerializer,EscalationRuleSerializer,
                          EscalationActionSerializer,EscalationPolicyVersionSerializer,
                          EscalationBindingSerializer)
from .models import (EscalationPolicy,EscalationRule,EscalationPolicyVersion,
                     SLAEscalationBinding)
from .escalation import EscalationPolicyService
from .services import CalendarService, SLAPolicyResolver, SLAPolicyService, require


class ActorMixin:
    read_permission="sla_policy.view";write_permission="sla_policy.manage"
    def actor(self):return self.request.user.employee
    def initial(self,request,*args,**kwargs):super().initial(request,*args,**kwargs);require(self.actor(),request.user,self.read_permission if request.method in {"GET","HEAD","OPTIONS"} else self.write_permission)


class CalendarViewSet(ActorMixin,viewsets.ModelViewSet):
    read_permission="sla_calendar.view";write_permission="sla_calendar.manage";queryset=BusinessCalendar.objects.select_related("current_version","created_by").prefetch_related("working_intervals","exceptions__intervals");serializer_class=BusinessCalendarSerializer;http_method_names=["get","post","patch","delete","head","options"]
    def destroy(self,*args,**kwargs):from rest_framework.exceptions import MethodNotAllowed;raise MethodNotAllowed("DELETE")
    def perform_create(self,s):
        CalendarService._validate_timezone(s.validated_data["timezone"]);obj=s.save(created_by=self.actor());AuditService.record(action="sla.calendar.created",entity=obj,actor_user=self.request.user,actor_employee=self.actor())
    def perform_update(self,s):
        CalendarService._validate_timezone(s.validated_data.get("timezone",s.instance.timezone));obj=s.save();AuditService.record(action="sla.calendar.updated",entity=obj,actor_user=self.request.user,actor_employee=self.actor())
    @action(detail=True,methods=["post"])
    def publish(self,request,pk=None):return Response(CalendarVersionSerializer(CalendarService.publish(calendar=self.get_object(),actor=self.actor(),user=request.user)).data,status=201)
    @action(detail=True,methods=["post"])
    def deactivate(self,request,pk=None):
        obj=self.get_object();obj.is_active=False;obj.save(update_fields=["is_active","updated_at"]);AuditService.record(action="sla.calendar.deactivated",entity=obj,actor_user=request.user,actor_employee=self.actor());return Response(self.get_serializer(obj).data)
    @action(detail=True,methods=["get","post"],url_path="working-intervals")
    def intervals(self,request,pk=None):
        calendar=self.get_object()
        if request.method=="GET":return Response(WorkingIntervalSerializer(calendar.working_intervals.all(),many=True).data)
        s=WorkingIntervalSerializer(data=request.data);s.is_valid(raise_exception=True);obj=CalendarService.save_interval(calendar=calendar,actor=self.actor(),user=request.user,**s.validated_data);return Response(WorkingIntervalSerializer(obj).data,status=201)
    @action(detail=True,methods=["patch","delete"],url_path=r"working-intervals/(?P<interval_id>[^/.]+)")
    def interval_detail(self,request,pk=None,interval_id=None):
        calendar=self.get_object();obj=get_object_or_404(calendar.working_intervals,pk=interval_id)
        if request.method=="DELETE":obj.delete();AuditService.record(action="sla.calendar.updated",entity=calendar,actor_user=request.user,actor_employee=self.actor());return Response(status=204)
        s=WorkingIntervalSerializer(obj,data=request.data,partial=True);s.is_valid(raise_exception=True);obj=CalendarService.save_interval(calendar=calendar,instance=obj,actor=self.actor(),user=request.user,**s.validated_data);return Response(WorkingIntervalSerializer(obj).data)
    @action(detail=True,methods=["get","post"])
    def exceptions(self,request,pk=None):
        calendar=self.get_object()
        if request.method=="GET":return Response(CalendarExceptionSerializer(calendar.exceptions.prefetch_related("intervals"),many=True).data)
        s=CalendarExceptionSerializer(data=request.data);s.is_valid(raise_exception=True);data=dict(s.validated_data);intervals=data.pop("intervals",[]);obj=CalendarService.save_exception(calendar=calendar,actor=self.actor(),user=request.user,intervals=intervals,**data);return Response(CalendarExceptionSerializer(obj).data,status=201)
    @action(detail=True,methods=["patch","delete"],url_path=r"exceptions/(?P<exception_id>[^/.]+)")
    def exception_detail(self,request,pk=None,exception_id=None):
        calendar=self.get_object();obj=get_object_or_404(calendar.exceptions,pk=exception_id)
        if request.method=="DELETE":obj.delete();AuditService.record(action="sla.calendar.updated",entity=calendar,actor_user=request.user,actor_employee=self.actor());return Response(status=204)
        s=CalendarExceptionSerializer(obj,data=request.data,partial=True);s.is_valid(raise_exception=True);data=dict(s.validated_data);intervals=data.pop("intervals",[{"start_time":x.start_time,"end_time":x.end_time,"position":x.position} for x in obj.intervals.all()]);obj=CalendarService.save_exception(calendar=calendar,instance=obj,actor=self.actor(),user=request.user,intervals=intervals,**data);return Response(CalendarExceptionSerializer(obj).data)


class PolicyViewSet(ActorMixin,viewsets.ModelViewSet):
    queryset=SLAPolicy.objects.select_related("current_version","draft_calendar__current_version","created_by").prefetch_related("versions__warning_thresholds");serializer_class=SLAPolicySerializer;http_method_names=["get","post","patch","head","options"]
    def perform_create(self,s):obj=s.save(created_by=self.actor());AuditService.record(action="sla.policy.created",entity=obj,actor_user=self.request.user,actor_employee=self.actor())
    def perform_update(self,s):obj=s.save();AuditService.record(action="sla.policy.updated",entity=obj,actor_user=self.request.user,actor_employee=self.actor())
    @action(detail=True,methods=["post"])
    def publish(self,request,pk=None):
        require(self.actor(),request.user,"sla_policy.publish");serializer=PolicyPublishSerializer(data=request.data);serializer.is_valid(raise_exception=True);obj=SLAPolicyService.publish(policy=self.get_object(),actor=self.actor(),user=request.user,**serializer.validated_data);return Response(PolicyVersionSerializer(obj).data,status=201)
    @action(detail=True,methods=["post"])
    def deactivate(self,request,pk=None):
        obj=self.get_object();obj.is_active=False;obj.save(update_fields=["is_active","updated_at"]);AuditService.record(action="sla.policy.deactivated",entity=obj,actor_user=request.user,actor_employee=self.actor());DomainEventService.publish(event_type="sla.policy.deactivated",entity=obj,actor=request.user,payload={"policy_id":str(obj.pk)});return Response(self.get_serializer(obj).data)


class AssignmentRuleViewSet(ActorMixin,viewsets.ModelViewSet):
    read_permission="sla_assignment_rule.view";write_permission="sla_assignment_rule.manage";queryset=SLAPolicyAssignmentRule.objects.select_related("policy","request_type","service","legal_entity","org_unit","location");serializer_class=AssignmentRuleSerializer;http_method_names=["get","post","patch","head","options"]
    def perform_create(self,s):obj=s.save();AuditService.record(action="sla.assignment_rule.created",entity=obj,actor_user=self.request.user,actor_employee=self.actor());DomainEventService.publish(event_type="sla.assignment_rule.updated",entity=obj,actor=self.request.user,payload={"rule_id":str(obj.pk)})
    def perform_update(self,s):obj=s.save();AuditService.record(action="sla.assignment_rule.updated",entity=obj,actor_user=self.request.user,actor_employee=self.actor());DomainEventService.publish(event_type="sla.assignment_rule.updated",entity=obj,actor=self.request.user,payload={"rule_id":str(obj.pk)})
    @action(detail=True,methods=["post"])
    def deactivate(self,request,pk=None):obj=self.get_object();obj.is_active=False;obj.save(update_fields=["is_active","updated_at"]);AuditService.record(action="sla.assignment_rule.deactivated",entity=obj,actor_user=request.user,actor_employee=self.actor());DomainEventService.publish(event_type="sla.assignment_rule.updated",entity=obj,actor=request.user,payload={"rule_id":str(obj.pk),"is_active":False});return Response(self.get_serializer(obj).data)


class PreviewViewSet(ActorMixin,viewsets.GenericViewSet):
    read_permission="sla_policy.view";write_permission="sla_policy.view"
    @action(detail=False,methods=["post"],url_path="policy-preview")
    def policy_preview(self,request):
        s=PolicyPreviewSerializer(data=request.data);s.is_valid(raise_exception=True);version=SLAPolicyResolver.resolve(**s.validated_data)
        if version is None:return Response({"matched_policy":None})
        return Response({"matched_policy":str(version.policy_id),"policy_version":version.version,"response_duration":version.response_duration_seconds,"resolution_duration":version.resolution_duration_seconds,"calendar":str(version.business_calendar_version_id or ""),"time_mode":version.time_mode})
    @action(detail=False,methods=["post"],url_path="deadline-preview")
    def deadline_preview(self,request):
        s=DeadlinePreviewSerializer(data=request.data);s.is_valid(raise_exception=True);data=s.validated_data
        due=data["start_at"]+timedelta(seconds=data["duration_seconds"]) if data["time_mode"]==TimeMode.ELAPSED_TIME else BusinessTimeCalculator.add_business_duration(data["calendar"],data["start_at"],data["duration_seconds"])
        return Response({"due_at":due})
    @action(detail=False,methods=["post"],url_path="escalation-preview")
    def escalation_preview(self,request):
        version=get_object_or_404(__import__('sla.models',fromlist=['SLAPolicyVersion']).SLAPolicyVersion,pk=request.data.get("sla_policy_version"));binding=SLAEscalationBinding.objects.filter(sla_policy_version=version,is_active=True).select_related("escalation_policy_version__policy").first()
        if not binding:return Response({"matched_policy":None,"rules":[]})
        metric=request.data.get("metric");trigger=request.data.get("trigger_type");threshold=request.data.get("threshold_percent");rules=[x for x in binding.escalation_policy_version.rules_snapshot if (not metric or x["metric_type"]==metric) and (not trigger or x["trigger_type"]==trigger) and (threshold is None or x.get("threshold_percent")==int(threshold))]
        return Response({"matched_policy":str(binding.escalation_policy_version.policy_id),"version":binding.escalation_policy_version.version,"rules":rules})

class EscalationPolicyViewSet(ActorMixin,viewsets.ModelViewSet):
    read_permission="sla.escalation_policy.view";write_permission="sla.escalation_policy.manage";queryset=EscalationPolicy.objects.select_related("current_version","created_by").prefetch_related("draft_rules__actions");serializer_class=EscalationPolicySerializer;http_method_names=["get","post","patch","head","options"]
    def perform_create(self,s):obj=s.save(created_by=self.actor());AuditService.record(action="sla.escalation_policy.created",entity=obj,actor_user=self.request.user,actor_employee=self.actor())
    def perform_update(self,s):obj=s.save();AuditService.record(action="sla.escalation_policy.updated",entity=obj,actor_user=self.request.user,actor_employee=self.actor())
    @action(detail=True,methods=["post"])
    def publish(self,request,pk=None):require(self.actor(),request.user,"sla.escalation_policy.publish");return Response(EscalationPolicyVersionSerializer(EscalationPolicyService.publish(self.get_object(),self.actor(),request.user)).data,status=201)
    @action(detail=True,methods=["post"])
    def deactivate(self,request,pk=None):obj=self.get_object();obj.is_active=False;obj.save(update_fields=["is_active","updated_at"]);AuditService.record(action="sla.escalation_policy.deactivated",entity=obj,actor_user=request.user,actor_employee=self.actor());return Response(self.get_serializer(obj).data)
    @action(detail=True,methods=["get","post"])
    def rules(self,request,pk=None):
        policy=self.get_object()
        if request.method=="GET":return Response(EscalationRuleSerializer(policy.draft_rules.prefetch_related("actions"),many=True).data)
        s=EscalationRuleSerializer(data=request.data);s.is_valid(raise_exception=True);return Response(EscalationRuleSerializer(s.save(policy=policy)).data,status=201)
    @action(detail=True,methods=["patch","delete"],url_path=r"rules/(?P<rule_id>[^/.]+)")
    def rule_detail(self,request,pk=None,rule_id=None):
        obj=get_object_or_404(self.get_object().draft_rules,pk=rule_id)
        if request.method=="DELETE":obj.delete();return Response(status=204)
        s=EscalationRuleSerializer(obj,data=request.data,partial=True);s.is_valid(raise_exception=True);return Response(EscalationRuleSerializer(s.save()).data)
    @action(detail=True,methods=["get","post"],url_path=r"rules/(?P<rule_id>[^/.]+)/actions")
    def actions(self,request,pk=None,rule_id=None):
        rule=get_object_or_404(self.get_object().draft_rules,pk=rule_id)
        if request.method=="GET":return Response(EscalationActionSerializer(rule.actions.all(),many=True).data)
        s=EscalationActionSerializer(data=request.data);s.is_valid(raise_exception=True);return Response(EscalationActionSerializer(s.save(rule=rule)).data,status=201)
    @action(detail=True,methods=["patch","delete"],url_path=r"rules/(?P<rule_id>[^/.]+)/actions/(?P<action_id>[^/.]+)")
    def action_detail(self,request,pk=None,rule_id=None,action_id=None):
        rule=get_object_or_404(self.get_object().draft_rules,pk=rule_id);obj=get_object_or_404(rule.actions,pk=action_id)
        if request.method=="DELETE":obj.delete();return Response(status=204)
        s=EscalationActionSerializer(obj,data=request.data,partial=True);s.is_valid(raise_exception=True);return Response(EscalationActionSerializer(s.save()).data)

class EscalationPolicyVersionViewSet(ActorMixin,viewsets.ReadOnlyModelViewSet):
    read_permission="sla.escalation_policy.view";queryset=EscalationPolicyVersion.objects.select_related("policy","created_by");serializer_class=EscalationPolicyVersionSerializer
class EscalationBindingViewSet(ActorMixin,viewsets.ModelViewSet):
    read_permission="sla.escalation_binding.view";write_permission="sla.escalation_binding.manage";queryset=SLAEscalationBinding.objects.select_related("sla_policy_version","escalation_policy_version");serializer_class=EscalationBindingSerializer;http_method_names=["get","post","patch","head","options"]
    def perform_create(self,s):obj=s.save(created_by=self.actor());AuditService.record(action="sla.escalation_binding.created",entity=obj,actor_user=self.request.user,actor_employee=self.actor())
    def perform_update(self,s):obj=s.save();AuditService.record(action="sla.escalation_binding.updated",entity=obj,actor_user=self.request.user,actor_employee=self.actor())
