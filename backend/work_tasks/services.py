from __future__ import annotations

import uuid
from django.db import transaction
from django.utils import timezone

from audit.services import AuditService
from access_control.services import PermissionService
from employees.assignment import AssignmentResolver, AssignmentTargetAmbiguous, AssignmentTargetUnresolved
from events.services import DomainEventService
from .exceptions import TaskBusinessError, TaskValidationError, TaskVersionConflict
from .models import (
    AcceptancePolicy, CompletionPolicy, Task, TaskAssignmentHistory,
    TaskDeadlineHistory, TaskNumberSequence, TaskReviewHistory, TaskStatus,
    TaskStatusHistory, TaskWaitingPeriod, WaitingReason,
)
from .policies import TaskAccessPolicy
from .state_machine import TaskStateMachine


class TaskService:
    @staticmethod
    def _authorize(*, actor, actor_user, permission, task=None):
        if actor_user and actor_user.is_superuser:
            return
        allowed = PermissionService.has_permission(employee=actor, permission=permission, obj=task) if task else TaskAccessPolicy.allows(employee=actor, permission=permission)
        if not allowed:
            raise TaskBusinessError("Недостаточно прав для операции с задачей.", code="task_permission_denied")

    @staticmethod
    def _next_number():
        sequence, _ = TaskNumberSequence.objects.select_for_update().get_or_create(key="task")
        sequence.value += 1
        sequence.save(update_fields=["value"])
        return f"TASK-{sequence.value:06d}"

    @staticmethod
    def _resolve_one(target, *, required=True):
        if target is None:
            if required:
                raise TaskBusinessError("Не задана цель назначения.", code="task_assignment_unresolved")
            return None
        try:
            employees = AssignmentResolver.resolve(target)
        except AssignmentTargetUnresolved as exc:
            raise TaskBusinessError(str(exc), code="task_assignment_unresolved") from exc
        except AssignmentTargetAmbiguous as exc:
            raise TaskBusinessError(str(exc), code="task_assignment_ambiguous") from exc
        if len(employees) != 1:
            raise TaskBusinessError("Назначение должно однозначно определять одного сотрудника.", code="task_assignment_ambiguous")
        return employees[0]

    @staticmethod
    def _validate_dates(planned_start_at, due_at):
        if planned_start_at and due_at and planned_start_at > due_at:
            raise TaskValidationError("Плановая дата начала не может быть позже дедлайна.", code="task_deadline_invalid")

    @staticmethod
    def _validate_parent(task, parent):
        cursor = parent
        visited = set()
        while cursor:
            if task and cursor.pk == task.pk:
                raise TaskValidationError("Нельзя создать циклическую иерархию задач.", code="task_parent_cycle")
            if cursor.pk in visited:
                raise TaskValidationError("Обнаружен цикл в иерархии задач.", code="task_parent_cycle")
            visited.add(cursor.pk)
            cursor = cursor.parent

    @staticmethod
    def _payload(task, actor, **extra):
        data = {
            "task_id": str(task.pk), "task_number": task.number, "actor_id": str(actor.pk),
            "status": task.status, "priority": task.priority, "author_id": str(task.author_id),
            "responsible_employee_id": str(task.responsible_employee_id) if task.responsible_employee_id else None,
            "executor_employee_id": str(task.executor_employee_id) if task.executor_employee_id else None,
            "org_unit_id": str(task.org_unit_id) if task.org_unit_id else None,
            "legal_entity_id": str(task.legal_entity_id) if task.legal_entity_id else None,
            "location_id": str(task.location_id) if task.location_id else None,
            "occurred_at": timezone.now(),
        }
        data.update(extra)
        return data

    @classmethod
    def _record(cls, task, actor, actor_user, action, old=None, new=None, correlation_id=None, audit_action=None, **payload):
        AuditService.record(action=audit_action or action, entity=task, actor_user=actor_user, actor_employee=actor, old_value=old, new_value=new, correlation_id=correlation_id)
        DomainEventService.publish(event_type=action, entity=task, actor=actor_user, payload=cls._payload(task, actor, **payload), correlation_id=correlation_id)

    @staticmethod
    def _locked(task, version):
        locked = Task.objects.select_for_update().get(pk=task.pk)
        if version != locked.version:
            raise TaskVersionConflict(f"Версия задачи изменилась: ожидалась {version}, текущая {locked.version}.")
        return locked

    @classmethod
    def _transition(cls, task, to_status, actor, reason=""):
        old = task.status
        TaskStateMachine.validate(old, to_status)
        task.status = to_status
        task.version += 1
        TaskStatusHistory.objects.create(task=task, from_status=old, to_status=to_status, actor=actor, reason=reason)
        return old

    @classmethod
    @transaction.atomic
    def create(cls, *, actor, actor_user, title, description="", author=None, responsible_target=None, executor_target=None, correlation_id=None, **data):
        cls._authorize(actor=actor, actor_user=actor_user, permission="task.create")
        author = author or actor
        cls._validate_dates(data.get("planned_start_at"), data.get("due_at"))
        cls._validate_parent(None, data.get("parent"))
        task = Task.objects.create(number=cls._next_number(), title=title, description=description, author=author, responsible_target=responsible_target, executor_target=executor_target, created_by=actor_user, updated_by=actor_user, **data)
        TaskStatusHistory.objects.create(task=task, to_status=TaskStatus.DRAFT, actor=actor)
        cls._record(task, actor, actor_user, "task.created", new={"status": task.status}, correlation_id=correlation_id)
        return task

    @classmethod
    @transaction.atomic
    def update(cls, *, task, actor, actor_user, version, correlation_id=None, **changes):
        task = cls._locked(task, version)
        cls._authorize(actor=actor, actor_user=actor_user, permission="task.edit", task=task)
        allowed = {"title", "description", "priority", "planned_start_at", "parent", "org_unit", "legal_entity", "location", "acceptance_policy", "completion_policy"}
        if set(changes) - allowed:
            raise TaskValidationError("Попытка изменить защищённые поля задачи.", code="task_field_read_only")
        if task.status in {TaskStatus.COMPLETED, TaskStatus.CANCELLED}:
            raise TaskValidationError("Финальную задачу нельзя редактировать обычной командой.")
        cls._validate_dates(changes.get("planned_start_at", task.planned_start_at), task.due_at)
        cls._validate_parent(task, changes.get("parent", task.parent))
        old = {field: str(getattr(task, field)) for field in changes}
        for field, value in changes.items():
            setattr(task, field, value)
        task.version += 1
        task.updated_by = actor_user
        task.save(update_fields=[*changes, "version", "updated_by", "updated_at"])
        cls._record(task, actor, actor_user, "task.updated", old=old, new={field: str(value) for field, value in changes.items()}, correlation_id=correlation_id)
        return task

    @classmethod
    @transaction.atomic
    def publish(cls, *, task, actor, actor_user, version, correlation_id=None):
        task = cls._locked(task, version)
        cls._authorize(actor=actor, actor_user=actor_user, permission="task.assign", task=task)
        if not task.title or not task.author_id or not task.responsible_target_id:
            raise TaskValidationError("Для публикации нужны название, автор и ответственный.", code="task_publish_invalid")
        task.responsible_employee = cls._resolve_one(task.responsible_target)
        task.executor_employee = cls._resolve_one(task.executor_target, required=False)
        old = cls._transition(task, TaskStatus.OPEN, actor)
        task.initial_due_at = task.due_at
        task.updated_by = actor_user
        task.save(update_fields=["responsible_employee", "executor_employee", "status", "initial_due_at", "version", "updated_by", "updated_at"])
        cls._record(task, actor, actor_user, "task.published", old={"status": old}, new={"status": task.status}, correlation_id=correlation_id)
        cls._record(task, actor, actor_user, "task.assigned", new={"responsible_employee_id": str(task.responsible_employee_id), "executor_employee_id": str(task.executor_employee_id) if task.executor_employee_id else None}, correlation_id=correlation_id)
        return task

    @classmethod
    @transaction.atomic
    def start(cls, *, task, actor, actor_user, version, correlation_id=None):
        task = cls._locked(task, version)
        cls._authorize(actor=actor, actor_user=actor_user, permission="task.start", task=task)
        old = cls._transition(task, TaskStatus.IN_PROGRESS, actor)
        task.started_at = task.started_at or timezone.now()
        task.updated_by = actor_user
        task.save(update_fields=["status", "started_at", "version", "updated_by", "updated_at"])
        cls._record(task, actor, actor_user, "task.started", old={"status": old}, new={"status": task.status}, correlation_id=correlation_id)
        return task

    @classmethod
    @transaction.atomic
    def pause(cls, *, task, actor, actor_user, version, reason, comment="", expected_resume_at=None, correlation_id=None):
        task = cls._locked(task, version)
        cls._authorize(actor=actor, actor_user=actor_user, permission="task.pause", task=task)
        if not reason or (reason == WaitingReason.OTHER and not comment.strip()):
            raise TaskValidationError("Для ожидания OTHER обязателен комментарий.", code="task_waiting_reason_required")
        old = cls._transition(task, TaskStatus.WAITING, actor)
        task.waiting_reason, task.waiting_comment, task.expected_resume_at = reason, comment, expected_resume_at
        task.updated_by = actor_user
        task.save(update_fields=["status", "waiting_reason", "waiting_comment", "expected_resume_at", "version", "updated_by", "updated_at"])
        TaskWaitingPeriod.objects.create(task=task, reason=reason, comment=comment, expected_resume_at=expected_resume_at, started_by=actor)
        cls._record(task, actor, actor_user, "task.waiting", old={"status": old}, new={"status": task.status, "reason": reason}, correlation_id=correlation_id, audit_action="task.paused")
        return task

    @classmethod
    @transaction.atomic
    def resume(cls, *, task, actor, actor_user, version, correlation_id=None):
        task = cls._locked(task, version)
        cls._authorize(actor=actor, actor_user=actor_user, permission="task.pause", task=task)
        old = cls._transition(task, TaskStatus.IN_PROGRESS, actor)
        period = TaskWaitingPeriod.objects.select_for_update().get(task=task, ended_at__isnull=True)
        period.ended_at, period.ended_by = timezone.now(), actor
        period.save(update_fields=["ended_at", "ended_by"])
        task.waiting_reason, task.waiting_comment, task.expected_resume_at = "", "", None
        task.updated_by = actor_user
        task.save(update_fields=["status", "waiting_reason", "waiting_comment", "expected_resume_at", "version", "updated_by", "updated_at"])
        cls._record(task, actor, actor_user, "task.resumed", old={"status": old}, new={"status": task.status}, correlation_id=correlation_id)
        return task

    @classmethod
    def _ensure_children_complete(cls, task):
        from .models import TaskChecklistItem
        if TaskChecklistItem.objects.select_for_update().filter(checklist__task=task, checklist__removed_at__isnull=True, required=True, is_completed=False).exists():
            raise TaskValidationError("Обязательные пункты чек-листа не выполнены.", code="task_checklist_incomplete")
        if task.completion_policy == CompletionPolicy.ALL_CHILDREN_COMPLETED and task.children.exclude(status__in=(TaskStatus.COMPLETED, TaskStatus.CANCELLED)).exists():
            raise TaskValidationError("Сначала завершите активные подзадачи.", code="task_children_incomplete")

    @classmethod
    @transaction.atomic
    def complete(cls, *, task, actor, actor_user, version, completion_comment="", correlation_id=None):
        task = cls._locked(task, version)
        cls._authorize(actor=actor, actor_user=actor_user, permission="task.complete", task=task)
        cls._ensure_children_complete(task)
        target_status = TaskStatus.COMPLETED if task.acceptance_policy == AcceptancePolicy.NONE else TaskStatus.REVIEW
        old = cls._transition(task, target_status, actor)
        task.completion_comment = completion_comment
        if target_status == TaskStatus.COMPLETED:
            task.completed_at = timezone.now()
            event = "task.completed"
        else:
            TaskReviewHistory.objects.create(task=task, action=TaskReviewHistory.Action.SUBMITTED, actor=actor, comment=completion_comment)
            event = "task.sent_to_review"
        task.updated_by = actor_user
        task.save(update_fields=["status", "completion_comment", "completed_at", "version", "updated_by", "updated_at"])
        cls._record(task, actor, actor_user, event, old={"status": old}, new={"status": task.status}, correlation_id=correlation_id)
        return task

    @classmethod
    def _validate_reviewer(cls, task, actor):
        expected = task.author_id if task.acceptance_policy == AcceptancePolicy.AUTHOR else task.responsible_employee_id
        if actor.pk != expected:
            raise TaskValidationError("Сотрудник не соответствует политике приёмки.", code="task_review_not_allowed")

    @classmethod
    @transaction.atomic
    def accept(cls, *, task, actor, actor_user, version, comment="", correlation_id=None):
        task = cls._locked(task, version)
        cls._authorize(actor=actor, actor_user=actor_user, permission="task.accept", task=task)
        cls._validate_reviewer(task, actor)
        cls._ensure_children_complete(task)
        old = cls._transition(task, TaskStatus.COMPLETED, actor)
        task.completed_at = timezone.now()
        task.updated_by = actor_user
        task.save(update_fields=["status", "completed_at", "version", "updated_by", "updated_at"])
        TaskReviewHistory.objects.create(task=task, action=TaskReviewHistory.Action.ACCEPTED, actor=actor, comment=comment)
        cls._record(task, actor, actor_user, "task.review_accepted", old={"status": old}, new={"status": task.status}, correlation_id=correlation_id, audit_action="task.accepted")
        return task

    @classmethod
    @transaction.atomic
    def reject(cls, *, task, actor, actor_user, version, reason, correlation_id=None):
        if not reason.strip():
            raise TaskValidationError("Укажите причину возврата.", code="task_review_reason_required")
        task = cls._locked(task, version)
        cls._authorize(actor=actor, actor_user=actor_user, permission="task.reject", task=task)
        cls._validate_reviewer(task, actor)
        old = cls._transition(task, TaskStatus.IN_PROGRESS, actor, reason)
        task.updated_by = actor_user
        task.save(update_fields=["status", "version", "updated_by", "updated_at"])
        TaskReviewHistory.objects.create(task=task, action=TaskReviewHistory.Action.REJECTED, actor=actor, comment=reason)
        cls._record(task, actor, actor_user, "task.review_rejected", old={"status": old}, new={"status": task.status, "reason": reason}, correlation_id=correlation_id, reason=reason, audit_action="task.rejected")
        return task

    @classmethod
    @transaction.atomic
    def reopen(cls, *, task, actor, actor_user, version, reason, correlation_id=None):
        if not reason.strip():
            raise TaskValidationError("Укажите причину повторного открытия.", code="task_reopen_reason_required")
        task = cls._locked(task, version)
        cls._authorize(actor=actor, actor_user=actor_user, permission="task.reopen", task=task)
        old = cls._transition(task, TaskStatus.IN_PROGRESS, actor, reason)
        previous_completed_at = task.completed_at
        task.completed_at = None
        task.updated_by = actor_user
        task.save(update_fields=["status", "completed_at", "version", "updated_by", "updated_at"])
        cls._record(task, actor, actor_user, "task.reopened", old={"status": old, "completed_at": previous_completed_at}, new={"status": task.status}, correlation_id=correlation_id, reason=reason)
        return task

    @classmethod
    @transaction.atomic
    def cancel(cls, *, task, actor, actor_user, version, reason, correlation_id=None):
        if not reason.strip():
            raise TaskValidationError("Укажите причину отмены.", code="task_cancel_reason_required")
        task = cls._locked(task, version)
        cls._authorize(actor=actor, actor_user=actor_user, permission="task.cancel", task=task)
        old = cls._transition(task, TaskStatus.CANCELLED, actor, reason)
        if old == TaskStatus.WAITING:
            period = TaskWaitingPeriod.objects.select_for_update().get(task=task, ended_at__isnull=True)
            period.ended_at, period.ended_by = timezone.now(), actor
            period.save(update_fields=["ended_at", "ended_by"])
        task.cancelled_at = timezone.now()
        task.cancellation_reason = reason
        task.waiting_reason, task.waiting_comment, task.expected_resume_at = "", "", None
        task.updated_by = actor_user
        task.save(update_fields=["status", "cancelled_at", "cancellation_reason", "waiting_reason", "waiting_comment", "expected_resume_at", "version", "updated_by", "updated_at"])
        cls._record(task, actor, actor_user, "task.cancelled", old={"status": old}, new={"status": task.status, "reason": reason}, correlation_id=correlation_id, reason=reason)
        return task

    @classmethod
    @transaction.atomic
    def change_deadline(cls, *, task, actor, actor_user, version, new_due_at, reason="", correlation_id=None):
        task = cls._locked(task, version)
        cls._authorize(actor=actor, actor_user=actor_user, permission="task.change_deadline", task=task)
        cls._validate_dates(task.planned_start_at, new_due_at)
        requires_reason = task.status in {TaskStatus.IN_PROGRESS, TaskStatus.WAITING, TaskStatus.REVIEW} or task.is_overdue or (task.due_at and new_due_at and new_due_at > task.due_at)
        if requires_reason and not reason.strip():
            raise TaskValidationError("Для изменения срока обязательна причина.", code="task_deadline_reason_required")
        if task.status in {TaskStatus.COMPLETED, TaskStatus.CANCELLED}:
            raise TaskValidationError("Срок финальной задачи изменить нельзя.", code="task_deadline_invalid")
        old_due = task.due_at
        task.due_at = new_due_at
        task.version += 1
        task.updated_by = actor_user
        task.save(update_fields=["due_at", "version", "updated_by", "updated_at"])
        TaskDeadlineHistory.objects.create(task=task, old_due_at=old_due, new_due_at=new_due_at, changed_by=actor, reason=reason)
        cls._record(task, actor, actor_user, "task.deadline_changed", old={"due_at": old_due}, new={"due_at": new_due_at}, correlation_id=correlation_id, old_due_at=old_due, new_due_at=new_due_at, reason=reason)
        return task

    @classmethod
    @transaction.atomic
    def reassign(cls, *, task, actor, actor_user, version, assignment_type, new_target, reason="", correlation_id=None):
        task = cls._locked(task, version)
        cls._authorize(actor=actor, actor_user=actor_user, permission="task.reassign", task=task)
        if task.status in {TaskStatus.COMPLETED, TaskStatus.CANCELLED}:
            raise TaskValidationError("Финальную задачу нельзя переназначить.", code="task_assignment_invalid")
        requires_reason = task.status in {TaskStatus.IN_PROGRESS, TaskStatus.WAITING, TaskStatus.REVIEW} or task.is_overdue
        if requires_reason and not reason.strip():
            raise TaskValidationError("Для переназначения обязательна причина.", code="task_reassign_reason_required")
        if assignment_type not in TaskAssignmentHistory.Type.values:
            raise TaskValidationError("Неизвестный тип назначения.", code="task_assignment_invalid")
        new_employee = cls._resolve_one(new_target)
        target_field = f"{assignment_type}_target"
        employee_field = f"{assignment_type}_employee"
        old_target, old_employee = getattr(task, target_field), getattr(task, employee_field)
        setattr(task, target_field, new_target)
        setattr(task, employee_field, new_employee)
        task.version += 1
        task.updated_by = actor_user
        task.save(update_fields=[target_field, employee_field, "version", "updated_by", "updated_at"])
        TaskAssignmentHistory.objects.create(task=task, assignment_type=assignment_type, old_target=old_target, old_employee=old_employee, new_target=new_target, new_employee=new_employee, changed_by=actor, reason=reason)
        cls._record(task, actor, actor_user, "task.reassigned", old={"employee_id": str(old_employee.pk) if old_employee else None}, new={"employee_id": str(new_employee.pk)}, correlation_id=correlation_id, old_employee=str(old_employee.pk) if old_employee else None, new_employee=str(new_employee.pk), reason=reason)
        return task

    @classmethod
    @transaction.atomic
    def move_parent(cls, *, task, actor, actor_user, version, parent, correlation_id=None):
        task = cls._locked(task, version)
        cls._authorize(actor=actor, actor_user=actor_user, permission="task.edit", task=task)
        cls._validate_parent(task, parent)
        task.parent = parent
        task.version += 1
        task.updated_by = actor_user
        task.save(update_fields=["parent", "version", "updated_by", "updated_at"])
        cls._record(task, actor, actor_user, "task.updated", new={"parent_id": str(parent.pk) if parent else None}, correlation_id=correlation_id)
        return task
