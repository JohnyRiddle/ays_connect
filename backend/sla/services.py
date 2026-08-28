from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone

from access_control.services import PermissionService
from audit.services import AuditService
from events.services import DomainEventService

from .exceptions import SLAError, SLAPolicyAmbiguous
from .models import (BusinessCalendar, BusinessCalendarException,
                     BusinessCalendarExceptionInterval,
                     BusinessCalendarVersion,
                     BusinessCalendarWorkingInterval, CalendarExceptionType,
                     MetricType, SLAPolicy, SLAPolicyAssignmentRule,
                     SLAPolicyVersion, SLAWarningThreshold, TimeMode)


def require(actor,user,permission):
    if not (user and user.is_superuser) and not PermissionService.has_permission(employee=actor,permission=permission):raise PermissionDenied("Insufficient SLA permission.")


class CalendarService:
    @staticmethod
    def _times(intervals):return [{"start":x.start_time.strftime("%H:%M:%S"),"end":x.end_time.strftime("%H:%M:%S"),"position":x.position} for x in intervals]
    @staticmethod
    def _validate_timezone(value):
        try:ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:raise SLAError("Unknown IANA timezone.",code="sla_calendar_invalid") from exc
    @staticmethod
    def _validate_intervals(intervals):
        ordered=sorted(intervals,key=lambda x:(x.start_time,x.end_time))
        for item in ordered:
            if item.start_time>=item.end_time:raise SLAError("Interval start must be before end.",code="sla_calendar_invalid")
        for previous,current in zip(ordered,ordered[1:]):
            if current.start_time<previous.end_time:raise SLAError("Working intervals overlap.",code="sla_calendar_overlap")
    @classmethod
    @transaction.atomic
    def save_interval(cls,*,calendar,actor,user,instance=None,**data):
        require(actor,user,"sla_calendar.manage");candidate=instance or BusinessCalendarWorkingInterval(calendar=calendar)
        for key,value in data.items():setattr(candidate,key,value)
        peers=list(calendar.working_intervals.filter(weekday=candidate.weekday,is_active=True).exclude(pk=candidate.pk));cls._validate_intervals([*peers,candidate]);candidate.full_clean();candidate.save();AuditService.record(action="sla.calendar.updated",entity=calendar,actor_user=user,actor_employee=actor);return candidate
    @classmethod
    @transaction.atomic
    def save_exception(cls,*,calendar,actor,user,intervals=(),instance=None,**data):
        require(actor,user,"sla_calendar.manage");exception=instance or BusinessCalendarException(calendar=calendar,created_by=actor)
        for key,value in data.items():setattr(exception,key,value)
        if not instance and calendar.exceptions.filter(date=exception.date).exists():raise SLAError("Conflicting exception for date.",code="sla_calendar_exception_conflict")
        parsed=[]
        for index,item in enumerate(intervals):parsed.append(BusinessCalendarExceptionInterval(exception=exception,start_time=item["start_time"],end_time=item["end_time"],position=item.get("position",index)))
        if exception.exception_type==CalendarExceptionType.NON_WORKING_DAY and parsed:raise SLAError("Non-working day cannot have intervals.",code="sla_calendar_invalid")
        if exception.exception_type==CalendarExceptionType.CUSTOM_HOURS and not parsed:raise SLAError("Custom hours require intervals.",code="sla_calendar_invalid")
        cls._validate_intervals(parsed);exception.save();exception.intervals.all().delete();BusinessCalendarExceptionInterval.objects.bulk_create(parsed);AuditService.record(action="sla.calendar.updated",entity=calendar,actor_user=user,actor_employee=actor);return exception
    @classmethod
    @transaction.atomic
    def publish(cls,*,calendar,actor,user):
        require(actor,user,"sla_calendar.manage");source_calendar=calendar;calendar=BusinessCalendar.objects.select_for_update().get(pk=calendar.pk);cls._validate_timezone(calendar.timezone)
        schedule={}
        for weekday in range(7):
            intervals=list(calendar.working_intervals.filter(weekday=weekday,is_active=True));cls._validate_intervals(intervals);schedule[str(weekday)]=cls._times(intervals)
        exceptions={}
        for item in calendar.exceptions.prefetch_related("intervals"):
            intervals=list(item.intervals.all());cls._validate_intervals(intervals)
            if item.exception_type==CalendarExceptionType.CUSTOM_HOURS and not intervals:raise SLAError("Custom hours require intervals.",code="sla_calendar_invalid")
            exceptions[item.date.isoformat()]={"type":item.exception_type,"name":item.name,"intervals":cls._times(intervals)}
        version=(calendar.versions.aggregate(v=Max("version"))["v"] or 0)+1;obj=BusinessCalendarVersion.objects.create(calendar=calendar,version=version,timezone=calendar.timezone,schedule_snapshot=schedule,exceptions_snapshot=exceptions,created_by=actor);calendar.current_version=obj;calendar.save(update_fields=["current_version","updated_at"])
        # Keep the caller's instance usable immediately after publishing. The
        # row lock above intentionally loads a separate model instance.
        source_calendar.current_version=obj
        AuditService.record(action="sla.calendar.version_published",entity=calendar,actor_user=user,actor_employee=actor,new_value={"version":version});DomainEventService.publish(event_type="sla.calendar.version_published",entity=calendar,actor=user,payload={"calendar_id":str(calendar.pk),"version":version});return obj


class SLAPolicyService:
    @staticmethod
    def _validate(policy):
        if policy.draft_time_mode==TimeMode.BUSINESS_TIME and (not policy.draft_calendar_id or not policy.draft_calendar.current_version_id):raise SLAError("Published calendar is required for business time.",code="sla_policy_calendar_required")
        if policy.draft_time_mode==TimeMode.ELAPSED_TIME and policy.draft_calendar_id:raise SLAError("Elapsed-time policy cannot reference calendar.",code="sla_policy_invalid")
        if not policy.draft_response_duration_seconds and not policy.draft_resolution_duration_seconds:raise SLAError("At least one SLA duration is required.",code="sla_policy_invalid")
        seen=set()
        for index,item in enumerate(policy.draft_thresholds):
            metric=item.get("metric_type");percent=item.get("threshold_percent")
            if metric not in MetricType.values or not isinstance(percent,int) or not 0<percent<=100 or (metric,percent) in seen:raise SLAError("Invalid or duplicate warning threshold.",code="sla_policy_threshold_invalid")
            seen.add((metric,percent))
    @classmethod
    @transaction.atomic
    def publish(cls,*,policy,actor,user,effective_from=None,effective_to=None):
        require(actor,user,"sla_policy.publish");policy=SLAPolicy.objects.select_for_update().get(pk=policy.pk);cls._validate(policy)
        if effective_from and effective_to and effective_from>=effective_to:raise SLAError("Invalid effective interval.",code="sla_policy_invalid")
        version=(policy.versions.aggregate(v=Max("version"))["v"] or 0)+1;obj=SLAPolicyVersion.objects.create(policy=policy,version=version,effective_from=effective_from,effective_to=effective_to,time_mode=policy.draft_time_mode,business_calendar_version=policy.draft_calendar.current_version if policy.draft_calendar_id else None,response_duration_seconds=policy.draft_response_duration_seconds,resolution_duration_seconds=policy.draft_resolution_duration_seconds,pause_policy=policy.draft_pause_policy,created_by=actor)
        SLAWarningThreshold.objects.bulk_create([SLAWarningThreshold(policy_version=obj,metric_type=item["metric_type"],threshold_percent=item["threshold_percent"],code=item.get("code",""),position=item.get("position",index)) for index,item in enumerate(policy.draft_thresholds)])
        policy.current_version=obj;policy.save(update_fields=["current_version","updated_at"]);AuditService.record(action="sla.policy.version_published",entity=policy,actor_user=user,actor_employee=actor,new_value={"version":version});DomainEventService.publish(event_type="sla.policy.version_published",entity=policy,actor=user,payload={"policy_id":str(policy.pk),"version":version});return obj


class SLAPolicyResolver:
    @staticmethod
    def resolve(*,request=None,request_type=None,service=None,priority=None,legal_entity=None,org_unit=None,location=None,at=None):
        if request:
            request_type=request.request_type;service=request.service;priority=request.priority;legal_entity=request.legal_entity;org_unit=request.org_unit;location=request.location;at=at or request.submitted_at or request.created_at
        service=service or (request_type.service if request_type else None);at=at or timezone.now()
        rules=SLAPolicyAssignmentRule.objects.filter(is_active=True,policy__is_active=True,policy__current_version__isnull=False).select_related("policy__current_version")
        rules=rules.filter(Q(request_type__isnull=True)|Q(request_type=request_type),Q(service__isnull=True)|Q(service=service),Q(request_priority="")|Q(request_priority=priority),Q(legal_entity__isnull=True)|Q(legal_entity=legal_entity),Q(org_unit__isnull=True)|Q(org_unit=org_unit),Q(location__isnull=True)|Q(location=location))
        ranked=[]
        for rule in rules:
            version=rule.policy.versions.filter(Q(effective_from__isnull=True)|Q(effective_from__lte=at),Q(effective_to__isnull=True)|Q(effective_to__gt=at)).order_by("-version").first()
            if version:
                specificity=sum(bool(value) for value in (rule.request_type_id,rule.service_id,rule.request_priority,rule.legal_entity_id,rule.org_unit_id,rule.location_id));ranked.append((specificity,rule.order,rule,version))
        if not ranked:return None
        ranked.sort(key=lambda x:(-x[0],x[1],str(x[2].pk)));best=ranked[0]
        if len(ranked)>1 and ranked[1][:2]==best[:2]:raise SLAPolicyAmbiguous("Equivalent SLA assignment rules matched.")
        return best[3]
