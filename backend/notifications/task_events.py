"""Materialize only task participants, with one intent per source event."""
from django.db import transaction
from django.utils import timezone
from employees.assignment_targets import assignable_employees
from events.models import OutboxEvent
from .models import NotificationIntent, Notification

TASK_EVENTS = {'task.created', 'task.published', 'task.assigned', 'task.reassigned', 'task.updated', 'task.started', 'task.waiting', 'task.resumed', 'task.deadline_changed', 'task.comment_added', 'task.comment_updated', 'task.comment_mentioned', 'task.watcher_added', 'task.overdue', 'task.completed', 'task.sent_to_review', 'task.review_accepted', 'task.review_rejected', 'task.reopened', 'task.cancelled'}
EVENT_LABELS = {'task.created': 'создана задача', 'task.published': 'задача опубликована', 'task.assigned': 'назначены участники', 'task.reassigned': 'изменено назначение', 'task.updated': 'изменены параметры задачи', 'task.started': 'задача в работе', 'task.waiting': 'задача приостановлена', 'task.resumed': 'работа возобновлена', 'task.deadline_changed': 'изменён срок', 'task.comment_added': 'новое сообщение', 'task.comment_updated': 'изменено сообщение', 'task.watcher_added': 'добавлен наблюдатель', 'task.overdue': 'задача просрочена', 'task.completed': 'задача завершена', 'task.sent_to_review': 'результат передан на приёмку', 'task.review_accepted': 'результат принят', 'task.review_rejected': 'результат отклонён', 'task.reopened': 'задача открыта повторно', 'task.cancelled': 'задача отменена'}


@transaction.atomic
def ingest_task_event(event):
    from work_tasks.models import Task, TaskComment
    from work_tasks.selectors import TaskSelector
    from work_tasks.routing import eligible_for_location
    from access_control.services import PermissionService
    from .services import NotificationChannelRouter
    payload = event.payload
    task = Task.objects.filter(pk=payload.get('task_id')).first()
    intent, _ = NotificationIntent.objects.select_for_update().get_or_create(source_event_id=event.event_id, defaults={'event_type': event.event_type, 'reason': 'WORK_TASK_EVENT', 'payload': {}})
    if intent.status == 'materialized':
        return intent
    if not task:
        intent.status = 'materialized'; intent.processed_at = timezone.now(); intent.save(); return intent
    recipients = {task.responsible_employee_id, task.executor_employee_id}
    recipients.update(task.watcher_records.filter(removed_at__isnull=True).values_list('employee_id', flat=True))
    comment = TaskComment.objects.filter(pk=payload.get('comment_id'), task=task, deleted_at__isnull=True).first() if payload.get('comment_id') else None
    if comment:
        recipients.update(comment.mention_records.values_list('employee_id', flat=True))
    # The message event already includes mentions. Keep mention Outbox history,
    # but never materialize a second notification for the same message.
    if event.event_type == 'task.comment_mentioned':
        recipients = set()
    actor = task.author.__class__.objects.filter(pk=payload.get('actor_id')).first() if payload.get('actor_id') else None
    intent.payload = {'task_id': str(task.pk), 'source_event_type': event.event_type, 'occurred_at': event.occurred_at.isoformat(), 'comment_id': str(comment.pk) if comment else None, 'is_internal': bool(comment and comment.is_internal), 'actor': {'id': str(actor.pk), 'name': actor.display_name} if actor else None}
    intent.save(update_fields=['payload'])
    for employee in assignable_employees().filter(pk__in=recipients, user__is_active=True).select_related('user'):
        if not TaskSelector.visible_to(employee).filter(pk=task.pk).exists() or not eligible_for_location(employee, task.location):
            continue
        if comment and comment.is_internal and not PermissionService.has_permission(employee=employee, permission='task.comment_internal', obj=task):
            continue
        # No attachments, inaccessible employee names or comment text in packets.
        message = f'{task.number}: {EVENT_LABELS.get(event.event_type, event.event_type)}'
        if comment and comment.mention_records.filter(employee=employee).exists():
            message += ' — вас упомянули в обсуждении'
        item, _ = Notification.objects.get_or_create(intent=intent, recipient_employee=employee, defaults={'recipient': employee.user, 'notification_type': 'task', 'priority': 'info', 'title': task.title, 'message': message, 'entity_type': 'Task', 'entity_id': str(task.pk), 'action_url': '/tasks/' + str(task.pk)})
        NotificationChannelRouter.route(item, 'WORK_TASK_EVENT')
    intent.status = 'materialized'; intent.processed_at = timezone.now(); intent.save(update_fields=['status', 'processed_at'])
    return intent
