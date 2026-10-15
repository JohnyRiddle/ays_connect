"""Independent comment approvals. No task lifecycle fields are stored or mutated here."""
import uuid
from django.db import models
from .models import Task, TaskComment


class ApprovalStatus(models.TextChoices):
    PENDING = 'PENDING', 'Ожидает согласования'
    CLARIFICATION_REQUESTED = 'CLARIFICATION_REQUESTED', 'Нужно уточнение'
    APPROVED = 'APPROVED', 'Согласовано'
    CANCELLED = 'CANCELLED', 'Отменено'


class TaskApproval(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.PROTECT, related_name='comment_approvals')
    comment = models.ForeignKey(TaskComment, on_delete=models.PROTECT, related_name='approvals')
    requester = models.ForeignKey('employees.Employee', on_delete=models.PROTECT, related_name='requested_task_approvals')
    approver = models.ForeignKey('employees.Employee', on_delete=models.PROTECT, related_name='assigned_task_approvals')
    source_body = models.TextField()
    source_internal = models.BooleanField(default=False)
    status = models.CharField(max_length=32, choices=ApprovalStatus.choices, default=ApprovalStatus.PENDING)
    round_number = models.PositiveIntegerField(default=1)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('created_at', 'id')
        constraints = [
            models.UniqueConstraint(fields=['comment', 'approver'], name='task_approval_comment_approver_unique'),
            models.CheckConstraint(condition=~models.Q(requester=models.F('approver')), name='task_approval_not_self'),
            models.CheckConstraint(condition=models.Q(status__in=ApprovalStatus.values), name='task_approval_status_valid'),
            models.CheckConstraint(condition=models.Q(round_number__gte=1, version__gte=1), name='task_approval_version_positive'),
        ]


class TaskApprovalEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    approval = models.ForeignKey(TaskApproval, on_delete=models.PROTECT, related_name='history')
    command_id = models.UUIDField(unique=True)
    sequence = models.PositiveIntegerField()
    round_number = models.PositiveIntegerField()
    actor = models.ForeignKey('employees.Employee', on_delete=models.PROTECT, related_name='task_approval_events')
    action = models.CharField(max_length=16, choices=[(x,x) for x in ['request','approve','clarify','resubmit','cancel']])
    from_status = models.CharField(max_length=32, blank=True)
    to_status = models.CharField(max_length=32, choices=ApprovalStatus.choices)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError('Approval history is immutable.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError('Approval history is immutable.')

    class Meta:
        ordering = ('sequence',)
        constraints = [
            models.UniqueConstraint(fields=['approval','sequence'], name='task_approval_history_sequence_unique'),
            models.CheckConstraint(condition=models.Q(sequence__gte=1, round_number__gte=1), name='task_approval_event_positive'),
            models.CheckConstraint(condition=~models.Q(text=''), name='task_approval_text_required'),
        ]
