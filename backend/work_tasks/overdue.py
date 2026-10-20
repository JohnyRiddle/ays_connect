from django.db import transaction
from django.utils import timezone
from events.services import DomainEventService
from audit.services import AuditService
from .models import Task, TaskOverdueNotice


def process_overdue(limit=100):
    from django.db.models import Exists, OuterRef
    count = 0
    from .selectors import TaskSelector
    from .services import TaskService
    from .exceptions import TaskVersionConflict
    noticed = TaskOverdueNotice.objects.filter(task_id=OuterRef('pk'), due_at=OuterRef('effective_deadline'))
    pending = TaskSelector.with_effective_deadline(Task.objects.filter(deleted_at__isnull=True)).filter(effective_deadline__lt=timezone.now()).exclude(status__in=['draft', 'completed', 'cancelled']).annotate(already_noticed=Exists(noticed)).filter(already_noticed=False).order_by('effective_deadline', 'pk')
    for pk in pending.values_list('pk', flat=True)[:limit]:
        with transaction.atomic():
            task = Task.objects.get(pk=pk)
            try:
                task = TaskService._locked(task, task.version, allow_deleted=True)
            except TaskVersionConflict:
                continue
            if not task.is_overdue:
                continue
            due = task.effective_due_at
            notice, created = TaskOverdueNotice.objects.get_or_create(task=task, due_at=due)
            if created:
                AuditService.record(action='task.overdue', entity=task, metadata={'due_at': due.isoformat()})
                DomainEventService.publish(event_type='task.overdue', entity=task, payload={'task_id': str(task.pk), 'task_number': task.number, 'due_at': due})
                count += 1
    return count
