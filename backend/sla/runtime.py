from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone

from audit.services import AuditService
from events.services import DomainEventService
from service_requests.models import RequestStatus, ServiceRequest

from .calendars import BusinessTimeCalculator
from .exceptions import SLAPolicyAmbiguous
from .models import (MetricType, PausePolicy, SLAInstance, SLAInstanceStatus,
                     SLAMetricInstance, SLAMetricStatus, SLAPausePeriod,
                     SLAResolutionCycle, SLAThresholdEvent, TimeMode)
from .services import SLAPolicyResolver


def _deadline(version,start,duration):
    if not duration:return None
    if version.time_mode==TimeMode.BUSINESS_TIME:return BusinessTimeCalculator.add_business_duration(version.business_calendar_version,start,duration)
    return start+timedelta(seconds=duration)


def _emit(instance,action,event_at,metric=None,threshold=None,actor_user=None,actor=None):
    payload={"sla_instance_id":str(instance.pk),"request_id":str(instance.request_id),"policy_version_id":str(instance.policy_version_id),"metric_type":metric.metric_type if metric else None,"resolution_cycle":metric.resolution_cycle.cycle_number if metric and metric.resolution_cycle_id else None,"threshold_percent":threshold,"event_at":event_at}
    AuditService.record(action=action,entity=instance,actor_user=actor_user,actor_employee=actor,new_value=payload)
    DomainEventService.publish(event_type=action,entity=instance,actor=actor_user,payload=payload)


class SLAInstanceService:
    @classmethod
    @transaction.atomic
    def create_for_request(cls,request,actor=None,actor_user=None):
        request=ServiceRequest.objects.select_for_update().get(pk=request.pk)
        existing=SLAInstance.objects.filter(request=request).first()
        if existing:return existing
        try:version=SLAPolicyResolver.resolve(request=request,at=request.submitted_at)
        except SLAPolicyAmbiguous:
            AuditService.record(action="sla.configuration.issue",entity=request,actor_user=actor_user,actor_employee=actor,new_value={"request_id":str(request.pk),"code":"sla_policy_ambiguous"})
            return None
        if not version:return None
        instance=SLAInstance.objects.create(request=request,policy_version=version,calendar_version=version.business_calendar_version,started_at=request.submitted_at,status=SLAInstanceStatus.ACTIVE)
        if version.response_duration_seconds:
            SLAMetricInstance.objects.create(sla_instance=instance,metric_type=MetricType.RESPONSE,duration_seconds=version.response_duration_seconds,started_at=request.submitted_at,due_at=_deadline(version,request.submitted_at,version.response_duration_seconds))
        if version.resolution_duration_seconds:cls._new_cycle(instance,request.submitted_at)
        _emit(instance,"sla.instance.created",request.submitted_at,actor_user=actor_user,actor=actor)
        from .escalation import EscalationInstanceService
        EscalationInstanceService.create_for_sla(instance)
        return instance

    @staticmethod
    def _new_cycle(instance,started_at):
        number=(instance.resolution_cycles.aggregate(v=Max("cycle_number"))["v"] or 0)+1
        due=_deadline(instance.policy_version,started_at,instance.policy_version.resolution_duration_seconds)
        cycle=SLAResolutionCycle.objects.create(sla_instance=instance,cycle_number=number,started_at=started_at,due_at=due)
        metric=SLAMetricInstance.objects.create(sla_instance=instance,resolution_cycle=cycle,metric_type=MetricType.RESOLUTION,duration_seconds=instance.policy_version.resolution_duration_seconds,started_at=started_at,due_at=due)
        return cycle,metric

    @classmethod
    @transaction.atomic
    def handle_lifecycle(cls,request,event_at=None,actor=None,actor_user=None,previous_status=None):
        event_at=event_at or timezone.now();instance=SLAInstance.objects.select_for_update().filter(request=request).first()
        if not instance:return None
        if request.status==RequestStatus.IN_PROGRESS:
            if previous_status in {RequestStatus.RESOLVED,RequestStatus.CLOSED}:
                cycle,metric=cls._new_cycle(instance,request.reopened_at or event_at);instance.status=SLAInstanceStatus.ACTIVE;instance.version+=1;instance.save(update_fields=["status","version","updated_at"]);_emit(instance,"sla.resolution.cycle_created",cycle.started_at,metric,actor_user=actor_user,actor=actor)
            elif previous_status in {RequestStatus.WAITING_REQUESTER,RequestStatus.WAITING_EXTERNAL}:cls.resume(instance,event_at,actor,actor_user)
            response=instance.metrics.filter(metric_type=MetricType.RESPONSE).first()
            if response and not response.achieved_at:cls.achieve_metric(response,request.started_at or event_at,actor,actor_user)
        elif request.status in {RequestStatus.WAITING_REQUESTER,RequestStatus.WAITING_EXTERNAL}:cls.pause(instance,request.status,event_at,actor,actor_user)
        elif request.status==RequestStatus.RESOLVED:
            metric=instance.metrics.filter(metric_type=MetricType.RESOLUTION,achieved_at__isnull=True).order_by("-resolution_cycle__cycle_number").first()
            if metric:cls.achieve_metric(metric,request.resolved_at or event_at,actor,actor_user)
            instance.status=SLAInstanceStatus.COMPLETED;instance.version+=1;instance.save(update_fields=["status","version","updated_at"])
        elif request.status==RequestStatus.CANCELLED:
            instance.metrics.filter(achieved_at__isnull=True).update(status=SLAMetricStatus.CANCELLED,updated_at=event_at);instance.status=SLAInstanceStatus.CANCELLED;instance.version+=1;instance.save(update_fields=["status","version","updated_at"]);_emit(instance,"sla.instance.cancelled",request.cancelled_at or event_at,actor_user=actor_user,actor=actor)
            from .models import EscalationSchedule, EscalationScheduleStatus
            EscalationSchedule.objects.filter(escalation_instance__sla_instance=instance,status=EscalationScheduleStatus.PENDING).update(status=EscalationScheduleStatus.CANCELLED,updated_at=event_at)
        return instance

    @staticmethod
    def _pause_allowed(policy,status):
        return policy==PausePolicy.BOTH or policy==status

    @classmethod
    def pause(cls,instance,reason,at,actor=None,actor_user=None):
        if not cls._pause_allowed(instance.policy_version.pause_policy,reason):return None
        active=instance.pause_periods.filter(ended_at__isnull=True).first()
        if active:return active
        metric=instance.metrics.filter(metric_type=MetricType.RESOLUTION,achieved_at__isnull=True).order_by("-resolution_cycle__cycle_number").first()
        if not metric:return None
        pause=SLAPausePeriod.objects.create(sla_instance=instance,resolution_cycle=metric.resolution_cycle,reason=reason,started_at=at)
        metric.status=SLAMetricStatus.PAUSED;metric.save(update_fields=["status","updated_at"]);instance.status=SLAInstanceStatus.PAUSED;instance.version+=1;instance.save(update_fields=["status","version","updated_at"]);_emit(instance,"sla.resolution.paused",at,metric,actor_user=actor_user,actor=actor);return pause

    @classmethod
    def resume(cls,instance,at,actor=None,actor_user=None):
        pause=instance.pause_periods.select_for_update().filter(ended_at__isnull=True).first()
        if not pause:return None
        metric=pause.resolution_cycle.metric;elapsed=max(0,int((at-pause.started_at).total_seconds()));pause.ended_at=at;pause.elapsed_seconds=elapsed
        if instance.policy_version.time_mode==TimeMode.BUSINESS_TIME:
            pause.business_seconds=max(0,int(BusinessTimeCalculator.business_duration_between(instance.calendar_version,pause.started_at,at).total_seconds()))
            consumed=effective_consumed(metric,pause.started_at);remaining=max(0,metric.duration_seconds-consumed);metric.due_at=_deadline(instance.policy_version,at,remaining)
        else:metric.due_at=metric.due_at+timedelta(seconds=elapsed)
        pause.save(update_fields=["ended_at","elapsed_seconds","business_seconds"]);pause.resolution_cycle.due_at=metric.due_at;pause.resolution_cycle.save(update_fields=["due_at"]);metric.status=SLAMetricStatus.ACTIVE;metric.save(update_fields=["status","due_at","updated_at"]);instance.status=SLAInstanceStatus.ACTIVE;instance.version+=1;instance.save(update_fields=["status","version","updated_at"]);_emit(instance,"sla.resolution.resumed",at,metric,actor_user=actor_user,actor=actor);return pause

    @classmethod
    def achieve_metric(cls,metric,at,actor=None,actor_user=None):
        if metric.achieved_at:return metric
        SLARuntimeEvaluator.evaluate_metric(metric,at)
        metric.refresh_from_db();metric.achieved_at=at;metric.status=SLAMetricStatus.ACHIEVED;metric.save(update_fields=["achieved_at","status","updated_at"])
        if metric.resolution_cycle_id:metric.resolution_cycle.achieved_at=at;metric.resolution_cycle.breached_at=metric.breached_at;metric.resolution_cycle.save(update_fields=["achieved_at","breached_at"])
        from .models import EscalationSchedule, EscalationScheduleStatus
        EscalationSchedule.objects.filter(metric_instance=metric,status=EscalationScheduleStatus.PENDING).update(status=EscalationScheduleStatus.CANCELLED,updated_at=at)
        _emit(metric.sla_instance,f"sla.{metric.metric_type}.achieved",at,metric,actor_user=actor_user,actor=actor);return metric


def effective_consumed(metric,at):
    instance=metric.sla_instance;end=max(metric.started_at,at)
    if metric.resolution_cycle_id:
        active=metric.resolution_cycle.pause_periods.filter(ended_at__isnull=True,started_at__lt=end).order_by("started_at").first()
        if active:end=active.started_at
    if instance.policy_version.time_mode==TimeMode.BUSINESS_TIME:total=BusinessTimeCalculator.business_duration_between(instance.calendar_version,metric.started_at,end).total_seconds();paused=sum(p.business_seconds or 0 for p in metric.resolution_cycle.pause_periods.filter(ended_at__isnull=False,started_at__lt=end)) if metric.resolution_cycle_id else 0
    else:total=(end-metric.started_at).total_seconds();paused=sum(p.elapsed_seconds or 0 for p in metric.resolution_cycle.pause_periods.filter(ended_at__isnull=False,started_at__lt=end)) if metric.resolution_cycle_id else 0
    return max(0,int(total-paused))


def _threshold_at(metric,target_seconds):
    due=_deadline(metric.sla_instance.policy_version,metric.started_at,target_seconds)
    if not metric.resolution_cycle_id:return due
    for pause in metric.resolution_cycle.pause_periods.filter(ended_at__isnull=False).order_by("started_at"):
        if pause.started_at>=due:break
        remaining=max(0,target_seconds-effective_consumed(metric,pause.started_at));due=_deadline(metric.sla_instance.policy_version,pause.ended_at,remaining)
    return due


class SLARuntimeEvaluator:
    @classmethod
    @transaction.atomic
    def evaluate_instance(cls,instance,now=None):
        now=now or timezone.now();instance=SLAInstance.objects.select_for_update().get(pk=instance.pk);created=0
        for metric in instance.metrics.select_related("resolution_cycle").filter(achieved_at__isnull=True).exclude(status=SLAMetricStatus.CANCELLED):created+=cls.evaluate_metric(metric,now)
        return created
    @classmethod
    def evaluate_metric(cls,metric,now):
        if metric.achieved_at or metric.status==SLAMetricStatus.CANCELLED:return 0
        consumed=effective_consumed(metric,now);created=0
        thresholds=metric.sla_instance.policy_version.warning_thresholds.filter(metric_type=metric.metric_type)
        for threshold in thresholds:
            if consumed*100 < metric.duration_seconds*threshold.threshold_percent:continue
            reached=_threshold_at(metric,metric.duration_seconds*threshold.threshold_percent/100)
            event,was_created=SLAThresholdEvent.objects.get_or_create(metric_instance=metric,threshold=threshold,defaults={"threshold_percent":threshold.threshold_percent,"reached_at":reached})
            if not was_created:continue
            created+=1;action="sla.breached" if threshold.threshold_percent==100 else "sla.warning_reached";_emit(metric.sla_instance,action,reached,metric,threshold.threshold_percent)
            if threshold.threshold_percent==100:metric.breached_at=metric.due_at;metric.status=SLAMetricStatus.BREACHED
        if consumed>=metric.duration_seconds and not metric.breached_at:
            metric.breached_at=metric.due_at;metric.status=SLAMetricStatus.BREACHED;created+=1;_emit(metric.sla_instance,"sla.breached",metric.due_at,metric,100)
        metric.last_evaluated_at=now;metric.save(update_fields=["last_evaluated_at","breached_at","status","updated_at"])
        if metric.resolution_cycle_id and metric.breached_at:metric.resolution_cycle.breached_at=metric.breached_at;metric.resolution_cycle.save(update_fields=["breached_at"])
        return created


class SLAReconciliationService:
    @classmethod
    def reconcile_request(cls,request):
        instance=cls.create_for_request(request)
        if not instance:return None
        previous=None
        if request.status==RequestStatus.IN_PROGRESS:
            if instance.pause_periods.filter(ended_at__isnull=True).exists():previous=RequestStatus.WAITING_REQUESTER
            elif request.reopened_at and not instance.resolution_cycles.filter(started_at__gte=request.reopened_at).exists():previous=RequestStatus.RESOLVED
        cls.handle_lifecycle(request,event_at=request.resolved_at or request.started_at or request.updated_at,previous_status=previous)
        return instance
