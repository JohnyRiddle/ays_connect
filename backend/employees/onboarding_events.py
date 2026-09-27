"""People consumers of Work/People Outbox events; no account or role mutations."""
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from audit.services import AuditService
from events.models import OutboxEvent
from .models import Employee, EmployeeInvitation, OnboardingInstance, OnboardingStepInstance
from .onboarding_lifecycle import OnboardingService

EVENTS = ('task.reopened', 'task.review_rejected', 'people.invitation.expired')
RECEIPT = 'people.acceptance_event.handled'


def unique_event(key, event_type, entity, payload, *, causation=None):
    # Existing unique Outbox event_id is the durable idempotency boundary.
    return OutboxEvent.objects.get_or_create(
        event_id=uuid.uuid5(uuid.NAMESPACE_URL, 'ays-people-v1:' + key),
        defaults=dict(event_type=event_type, entity_type=type(entity).__name__,
                      entity_id=str(entity.pk), occurred_at=timezone.now(), payload=payload,
                      causation_id=causation),
    )[0]


def notify(key, entity, recipients, reason, payload, *, causation=None):
    active = Employee.objects.filter(pk__in=set(recipients), is_active=True,
                                     user__is_active=True).exclude(status='terminated')
    ids = list(active.values_list('pk', flat=True))
    for pk in ids:
        unique_event(f'{key}:{pk}', 'notification.requested', entity,
                     dict(payload, reason=reason, recipient_employee_id=str(pk)), causation=causation)
    if not ids:
        unique_event(key + ':no-recipient', 'people.notification.no_recipient', entity,
                     {'reason':reason}, causation=causation)


@transaction.atomic
def consume(event_id):
    event = OutboxEvent.objects.select_for_update().get(pk=event_id)
    if event.event_type not in EVENTS:
        return False
    if OutboxEvent.objects.filter(event_type=RECEIPT, causation_id=event.event_id).exists():
        return False
    outcome = 'handled'
    if event.event_type == 'people.invitation.expired':
        invitation = EmployeeInvitation.objects.get(pk=event.entity_id)
        recipients = Employee.objects.filter(user_id=invitation.created_by_id).values_list('pk',flat=True)
        notify(str(event.event_id), invitation, recipients, 'PEOPLE_INVITATION_EXPIRED',
               {'invitation_id':str(invitation.pk)}, causation=event.event_id)
    else:
        from work_tasks.models import Task
        linked = OnboardingStepInstance.objects.filter(task_id=event.entity_id).first()
        instance = owner = step = None
        if linked:
            owner = Employee.objects.select_for_update().get(pk=linked.onboarding.employee_id)
            instance = OnboardingInstance.objects.select_for_update().get(pk=linked.onboarding_id)
            step = OnboardingStepInstance.objects.select_for_update().get(pk=linked.pk)
        task = Task.objects.select_for_update().get(pk=event.entity_id)
        version = event.payload.get('task_version')
        # Legacy events have no version: never let them mutate a current snapshot.
        current = type(version) is int and version <= task.version and task.status in {'in_progress','waiting','review'}
        if not current:
            outcome = 'stale_transition'
        elif instance and owner.is_active and owner.status != 'terminated' and instance.status in {'pending','active','completed'} and step.status == 'completed':
            if instance.status == 'completed' and OnboardingInstance.objects.filter(
                employee=owner,status__in=['pending','active','paused']).exclude(pk=instance.pk).exists():
                key = str(event.event_id) + ':conflict'
                diagnostic_id = uuid.uuid5(uuid.NAMESPACE_URL, 'ays-people-v1:' + key)
                if not OutboxEvent.objects.filter(event_id=diagnostic_id).exists():
                    unique_event(key, 'people.onboarding.reopen_blocked', instance,
                                 {'code':'ONBOARDING_REOPEN_ACTIVE_INSTANCE_CONFLICT'}, causation=event.event_id)
                    AuditService.record(action='people.onboarding.reopen_blocked', entity=instance,
                        actor_user=get_user_model().objects.filter(pk=event.actor_id).first() if event.actor_id else None,
                        metadata={'source_event_id':str(event.event_id),'code':'ONBOARDING_REOPEN_ACTIVE_INSTANCE_CONFLICT'})
                    notify(key, instance, [step.responsible_employee_id], 'PEOPLE_ONBOARDING_REOPEN_BLOCKED',
                           {'onboarding_id':str(instance.pk)}, causation=event.event_id)
                # No receipt: after an authorized cancellation of B the same source can be retried.
                return False
            old = {'status':step.status,'completed_at':str(step.completed_at),'version':step.version}
            step.status='in_progress';step.completed_at=None;step.completed_by=None;step.version+=1
            step.save(update_fields=['status','completed_at','completed_by','version','updated_at'])
            instance.status='active';instance.completed_at=None;instance.version+=1
            instance.save(update_fields=['status','completed_at','version','updated_at'])
            AuditService.record(action='people.onboarding.step_reopened',entity=step,
                actor_user=get_user_model().objects.filter(pk=event.actor_id).first() if event.actor_id else None,
                old_value=old, new_value={'status':step.status}, metadata={'source_event_id':str(event.event_id)})
            OnboardingService.reconcile(instance)
        if current:
            actor = Employee.objects.filter(pk=event.payload.get('actor_id')).first()
            reason = 'WORK_TASK_REOPENED' if event.event_type == 'task.reopened' else 'WORK_TASK_REJECTED'
            notify(str(event.event_id),task,[task.executor_employee_id] if task.executor_employee_id else [], reason,
                   {'task_id':str(task.pk),'task_number':task.number,
                    'actor_name':actor.display_name if actor else '', 'reason_text':str(event.payload.get('reason',''))[:500]},
                   causation=event.event_id)
    unique_event(str(event.event_id)+':receipt',RECEIPT,event,{'outcome':outcome},causation=event.event_id)
    return True


def process_events(batch_size=100):
    handled = OutboxEvent.objects.filter(event_type=RECEIPT).values('causation_id')
    candidates = OutboxEvent.objects.filter(event_type__in=EVENTS).exclude(event_id__in=handled).order_by('created_at')
    count=0
    for pk in list(candidates.values_list('pk',flat=True)[:batch_size]):
        count += int(consume(pk))
    return count


@transaction.atomic
def notify_overdue(instance, now=None):
    now=now or timezone.now()
    interval=max(1,int(getattr(settings,'PEOPLE_OVERDUE_REPEAT_HOURS',24)))
    owner=Employee.objects.select_for_update().get(pk=instance.employee_id)
    instance=OnboardingInstance.objects.select_for_update().get(pk=instance.pk)
    if not owner.is_active or owner.status=='terminated' or instance.status not in {'pending','active'}:
        return
    for step in instance.steps.select_for_update().filter(due_at__lt=now,status__in=['pending','in_progress','blocked']):
        bucket=int((now-step.due_at).total_seconds() // timedelta(hours=interval).total_seconds())
        coordinator=Employee.objects.filter(user_id=instance.assigned_by_id).first()
        recipients=[pk for pk in [step.responsible_employee_id,coordinator.pk if coordinator else None] if pk]
        notify(f'overdue:{step.pk}:{step.due_at.isoformat()}:{bucket}',step,recipients,'PEOPLE_STEP_OVERDUE',
               {'onboarding_id':str(instance.pk),'step_title':step.title_snapshot})
