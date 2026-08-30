import logging
from datetime import timedelta

from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone

from audit.services import AuditService
from employees.assignment import AssignmentResolver
from events.services import DomainEventService
from service_requests.collaboration import RequestCollaborationService
from service_requests.models import RequestStatus
from service_requests.services import RequestBusinessError, ServiceRequestService

from .exceptions import SLAError
from .models import (EscalationActionType, EscalationExecution,
                     EscalationExecutionStatus, EscalationInstance,
                     EscalationInstanceStatus, EscalationPolicy,
                     EscalationPolicyVersion, EscalationSchedule,
                     EscalationScheduleStatus, EscalationTargetType,
                     EscalationTrigger, MetricType, SLAEscalationBinding,
                     SLAMetricInstance)

logger=logging.getLogger(__name__)


def _event(instance,event_type,payload=None):
    actor=instance.policy_version.created_by;data={"escalation_instance_id":str(instance.pk),"sla_instance_id":str(instance.sla_instance_id),"request_id":str(instance.sla_instance.request_id),**(payload or {})}
    AuditService.record(action=event_type,entity=instance,actor_user=actor.user,actor_employee=actor,new_value=data);DomainEventService.publish(event_type=event_type,entity=instance,actor=actor.user,payload=data)


class EscalationPolicyService:
    @staticmethod
    def _validate(policy):
        rules=list(policy.draft_rules.prefetch_related("actions"))
        if not rules:raise SLAError("Escalation policy requires at least one rule.",code="escalation_policy_invalid")
        snapshots=[];seen=set()
        for rule in rules:
            if rule.level<1 or not rule.actions.exists():raise SLAError("Rule requires positive level and actions.",code="escalation_rule_invalid")
            if rule.trigger_type==EscalationTrigger.ON_WARNING:
                if not rule.threshold_percent or not 0<rule.threshold_percent<100 or rule.delay_seconds:raise SLAError("Warning requires threshold 1..99.",code="escalation_rule_invalid")
            elif rule.trigger_type==EscalationTrigger.ON_BREACH:
                if rule.threshold_percent or rule.delay_seconds:raise SLAError("Breach rule cannot have threshold or delay.",code="escalation_rule_invalid")
            elif rule.trigger_type==EscalationTrigger.AFTER_BREACH_DURATION:
                if not rule.delay_seconds or rule.threshold_percent:raise SLAError("Delayed breach requires positive delay.",code="escalation_rule_invalid")
            key=(rule.trigger_type,rule.metric_type,rule.threshold_percent,rule.delay_seconds,rule.level,rule.position)
            if key in seen:raise SLAError("Duplicate escalation rule.",code="escalation_rule_invalid")
            seen.add(key);actions=[]
            for action in rule.actions.all():
                cfg=action.action_config or {};target_required=action.action_type in {EscalationActionType.REQUEST_NOTIFICATION,EscalationActionType.ADD_WATCHER}
                if target_required and not action.target_type:raise SLAError("Action target is required.",code="escalation_action_invalid")
                if action.target_type==EscalationTargetType.ASSIGNMENT_TARGET and not action.assignment_target_id:raise SLAError("Assignment target is required.",code="escalation_action_invalid")
                if action.action_type==EscalationActionType.CHANGE_PRIORITY and cfg.get("target_priority") not in {"low","normal","high","critical"}:raise SLAError("Target priority is required.",code="escalation_action_invalid")
                if action.action_type==EscalationActionType.REASSIGN and not action.assignment_target_id:raise SLAError("Reassign target is required.",code="escalation_action_invalid")
                actions.append({"key":str(action.pk),"action_type":action.action_type,"target_type":action.target_type,"assignment_target_id":str(action.assignment_target_id or ""),"target_config":action.target_config,"action_config":cfg,"position":action.position})
            snapshots.append({"key":str(rule.pk),"name":rule.name,"trigger_type":rule.trigger_type,"metric_type":rule.metric_type,"threshold_percent":rule.threshold_percent,"delay_seconds":rule.delay_seconds,"level":rule.level,"position":rule.position,"actions":actions})
        return snapshots
    @classmethod
    @transaction.atomic
    def publish(cls,policy,actor,user):
        policy=EscalationPolicy.objects.select_for_update().get(pk=policy.pk);snapshot=cls._validate(policy);version=(policy.versions.aggregate(v=Max("version"))["v"] or 0)+1;obj=EscalationPolicyVersion.objects.create(policy=policy,version=version,rules_snapshot=snapshot,created_by=actor);policy.current_version=obj;policy.save(update_fields=["current_version","updated_at"]);AuditService.record(action="sla.escalation_policy.version_published",entity=policy,actor_user=user,actor_employee=actor,new_value={"version":version});DomainEventService.publish(event_type="sla.escalation.policy_published",entity=policy,actor=user,payload={"policy_id":str(policy.pk),"version":version});return obj


class EscalationInstanceService:
    @classmethod
    @transaction.atomic
    def create_for_sla(cls,sla_instance):
        from .models import SLAInstance
        sla_instance=SLAInstance.objects.select_for_update().get(pk=sla_instance.pk);existing=EscalationInstance.objects.filter(sla_instance=sla_instance).first()
        if existing:return existing
        binding=SLAEscalationBinding.objects.filter(sla_policy_version=sla_instance.policy_version,is_active=True).filter(Q(effective_from__isnull=True)|Q(effective_from__lte=sla_instance.started_at)).select_related("escalation_policy_version").order_by("-effective_from","-created_at").first()
        if not binding:return None
        instance=EscalationInstance.objects.create(sla_instance=sla_instance,policy_version=binding.escalation_policy_version);_event(instance,"sla.escalation_instance.created");return instance


def _recipients(request,action):
    target=action.get("target_type");values=[]
    if target==EscalationTargetType.REQUEST_EXECUTOR:values=[request.assigned_employee]
    elif target==EscalationTargetType.REQUEST_RESPONSIBLE:values=[request.responsible_employee]
    elif target==EscalationTargetType.REQUEST_REQUESTER:values=[request.requester]
    elif target==EscalationTargetType.REQUEST_EXECUTOR_MANAGER:values=[request.assigned_employee.manager if request.assigned_employee else None]
    elif target==EscalationTargetType.REQUEST_RESPONSIBLE_MANAGER:values=[request.responsible_employee.manager if request.responsible_employee else None]
    elif target==EscalationTargetType.ASSIGNMENT_TARGET:
        from employees.models import AssignmentTarget
        assignment=AssignmentTarget.objects.filter(pk=action.get("assignment_target_id")).first()
        try:values=AssignmentResolver.resolve(assignment) if assignment else []
        except Exception:values=[]
    return sorted({x.pk:x for x in values if x and x.is_active}.values(),key=lambda x:str(x.pk))


class NotificationIntentActionHandler:
    @staticmethod
    def execute(execution,action,actor,user):
        recipients=_recipients(execution.escalation_instance.sla_instance.request,action)
        if not recipients:return "skipped",[],"target_not_found"
        for employee in recipients:
            DomainEventService.publish(event_type="notification.requested",entity=execution,actor=user,payload={"reason":"SLA_ESCALATION","recipient_employee_id":str(employee.pk),"request_id":str(execution.escalation_instance.sla_instance.request_id),"sla_instance_id":str(execution.escalation_instance.sla_instance_id),"escalation_instance_id":str(execution.escalation_instance_id),"escalation_execution_id":str(execution.pk),"level":execution.rule_snapshot["level"],"event_type":execution.trigger_type})
        return "succeeded",[str(x.pk) for x in recipients],""
class AddWatcherActionHandler:
    @staticmethod
    def execute(execution,action,actor,user):
        recipients=_recipients(execution.escalation_instance.sla_instance.request,action)
        if not recipients:return "skipped",[],"target_not_found"
        for employee in recipients:RequestCollaborationService.add_watcher(request=execution.escalation_instance.sla_instance.request,employee=employee,actor=actor,actor_user=user,system=True)
        return "succeeded",[str(x.pk) for x in recipients],""
class ChangePriorityActionHandler:
    @staticmethod
    def execute(execution,action,actor,user):
        request,changed=ServiceRequestService.escalation_change_priority(request=execution.escalation_instance.sla_instance.request,target_priority=action["action_config"]["target_priority"],actor=actor,actor_user=user);return ("succeeded" if changed else "skipped"),[],("" if changed else "already_higher_priority")
class ReassignActionHandler:
    @staticmethod
    def execute(execution,action,actor,user):
        from employees.models import AssignmentTarget
        target=AssignmentTarget.objects.filter(pk=action.get("assignment_target_id")).first()
        if not target:return "skipped",[],"target_not_found"
        try:request,changed=ServiceRequestService.escalation_reassign(request=execution.escalation_instance.sla_instance.request,target=target,actor=actor,actor_user=user)
        except RequestBusinessError as exc:return "skipped",[],getattr(exc,"code","domain_conflict")
        return ("succeeded" if changed else "skipped"),[],("" if changed else "already_assigned")


class EscalationActionExecutor:
    handlers={EscalationActionType.REQUEST_NOTIFICATION:NotificationIntentActionHandler,EscalationActionType.ADD_WATCHER:AddWatcherActionHandler,EscalationActionType.CHANGE_PRIORITY:ChangePriorityActionHandler,EscalationActionType.REASSIGN:ReassignActionHandler}
    @classmethod
    @transaction.atomic
    def execute(cls,execution):
        execution=EscalationExecution.objects.select_for_update().get(pk=execution.pk)
        if execution.status in {EscalationExecutionStatus.SUCCEEDED,EscalationExecutionStatus.SKIPPED}:return execution
        execution.status=EscalationExecutionStatus.RUNNING;execution.started_at=timezone.now();execution.save(update_fields=["status","started_at"]);actor=execution.escalation_instance.policy_version.created_by;user=actor.user
        try:
            with transaction.atomic():status,targets,error=cls.handlers[execution.action_type].execute(execution,execution.action_snapshot,actor,user)
            execution.status=status;execution.target_snapshot=targets;execution.error_code=error;execution.completed_at=timezone.now();execution.save(update_fields=["status","target_snapshot","error_code","completed_at"]);_event(execution.escalation_instance,f"sla.escalation.action.{status}",{"execution_id":str(execution.pk),"action_type":execution.action_type,"error_code":error});DomainEventService.publish(event_type="sla.escalation.action_completed",entity=execution,actor=user,payload={"execution_id":str(execution.pk),"status":status});return execution
        except Exception as exc:
            execution.status=EscalationExecutionStatus.FAILED;execution.error_code="internal_error";execution.completed_at=timezone.now();execution.save(update_fields=["status","error_code","completed_at"]);_event(execution.escalation_instance,"sla.escalation.action.failed",{"execution_id":str(execution.pk),"action_type":execution.action_type,"error_code":"internal_error"});raise


class EscalationRuntimeService:
    @staticmethod
    def _terminal_for_delay(metric):return bool(metric.achieved_at) or metric.sla_instance.request.status==RequestStatus.CANCELLED
    @classmethod
    @transaction.atomic
    def _execution(cls,instance,metric,rule,action,triggered_at,due_at=None):
        execution,_=EscalationExecution.objects.get_or_create(escalation_instance=instance,metric_instance=metric,rule_key=rule["key"],action_key=action["key"],defaults={"resolution_cycle":metric.resolution_cycle,"rule_snapshot":rule,"action_snapshot":action,"trigger_type":rule["trigger_type"],"triggered_at":triggered_at,"due_at":due_at,"action_type":action["action_type"]})
        return EscalationActionExecutor.execute(execution)
    @classmethod
    def process_instance(cls,instance,now=None):
        now=now or timezone.now();instance=EscalationInstance.objects.select_related("sla_instance__request","policy_version").get(pk=instance.pk);count=0
        for metric in instance.sla_instance.metrics.prefetch_related("threshold_events").all():
            for rule in instance.policy_version.rules_snapshot:
                if rule["metric_type"]!=metric.metric_type:continue
                trigger=None
                if rule["trigger_type"]==EscalationTrigger.ON_WARNING:
                    event=metric.threshold_events.filter(threshold_percent=rule["threshold_percent"]).first();trigger=event.reached_at if event else None
                elif rule["trigger_type"]==EscalationTrigger.ON_BREACH:trigger=metric.breached_at
                elif metric.breached_at:
                    due=metric.breached_at+timedelta(seconds=rule["delay_seconds"]);schedule,_=EscalationSchedule.objects.get_or_create(escalation_instance=instance,metric_instance=metric,rule_key=rule["key"],defaults={"rule_snapshot":rule,"due_at":due})
                    if cls._terminal_for_delay(metric) and schedule.status==EscalationScheduleStatus.PENDING:schedule.status=EscalationScheduleStatus.CANCELLED;schedule.save(update_fields=["status","updated_at"])
                    elif schedule.status==EscalationScheduleStatus.PENDING and due<=now:
                        schedule.status=EscalationScheduleStatus.PROCESSING;schedule.save(update_fields=["status","updated_at"])
                        for action in rule["actions"]:cls._execution(instance,metric,rule,action,due,due);count+=1
                        schedule.status=EscalationScheduleStatus.COMPLETED;schedule.save(update_fields=["status","updated_at"])
                    continue
                if trigger:
                    for action in rule["actions"]:cls._execution(instance,metric,rule,action,trigger);count+=1
        if instance.sla_instance.status in {"completed","cancelled"} and not instance.schedules.filter(status=EscalationScheduleStatus.PENDING).exists():instance.status=EscalationInstanceStatus.CANCELLED if instance.sla_instance.status=="cancelled" else EscalationInstanceStatus.COMPLETED;instance.version+=1;instance.save(update_fields=["status","version","updated_at"])
        return count


class EscalationReconciliationService:
    @classmethod
    def reconcile_sla(cls,sla_instance,now=None):
        instance=EscalationInstanceService.create_for_sla(sla_instance)
        if instance:
            instance.executions.filter(status=EscalationExecutionStatus.RUNNING).update(status=EscalationExecutionStatus.FAILED,error_code="interrupted_execution",completed_at=now or timezone.now())
            EscalationRuntimeService.process_instance(instance,now)
        return instance
