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
    def _work_ready(task):
        from .routing import department_head, validate_member
        if not task.responsible_department:
            raise TaskValidationError('Администратор должен явно заполнить ответственное подразделение.', code='task_department_required')
        if not task.responsible_employee or department_head(task.responsible_department).pk != task.responsible_employee_id:
            raise TaskValidationError('До передачи в работу определите текущего руководителя подразделения.', code='task_department_responsible_invalid')
        validate_member(task.responsible_employee, task.responsible_department, task.location)
        if task.executor_employee:
            validate_member(task.executor_employee, task.responsible_department, task.location)
    @staticmethod
    def _assignment_administrator(actor, actor_user, task):
        if actor_user and actor_user.is_superuser:
            return True
        if PermissionService.has_permission(employee=actor, permission='task.admin', obj=task):
            return True
        from access_control.models import Scope
        return any(grant.role.permission_grants.filter(permission__code='task.reassign', scope=Scope.GLOBAL).exists() for grant in TaskAccessPolicy._grants(actor, 'task.reassign'))
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
            "task_id": str(task.pk), "task_number": task.number, "actor_id": str(actor.pk), "task_version": task.version,
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
        from projects.models import ProjectTaskLink
        from projects.services import project_lock
        project_id = ProjectTaskLink.objects.filter(task_id=task.pk, is_active=True).values_list('project_id', flat=True).first()
        if project_id:
            project_lock(project_id)
        locked = Task.objects.select_for_update().get(pk=task.pk)
        if ProjectTaskLink.objects.filter(task_id=task.pk, is_active=True).values_list('project_id', flat=True).first() != project_id:
            raise TaskVersionConflict('Связь задачи с проектом изменилась; повторите операцию.')
        if version != locked.version:
            raise TaskVersionConflict(f"Версия задачи изменилась: ожидалась {version}, текущая {locked.version}.")
        return locked

    @classmethod
    def _transition(cls, task, to_status, actor, reason=""):
        old = task.status
        TaskStateMachine.validate(old, to_status)
        if to_status == TaskStatus.IN_PROGRESS:
            cls._work_ready(task)
        task.status = to_status
        task.version += 1
        TaskStatusHistory.objects.create(task=task, from_status=old, to_status=to_status, actor=actor, reason=reason)
        return old

    @classmethod
    @transaction.atomic
    def create(cls, *, actor, actor_user, title, description="", author=None, responsible_target=None, executor_target=None, correlation_id=None, **data):
        cls._authorize(actor=actor, actor_user=actor_user, permission="task.create")
        author = author or actor
        from organizations.object_services import require_available_location
        require_available_location(data.get("location"), actor_user)
        cls._validate_dates(data.get("planned_start_at"), data.get("due_at"))
        cls._validate_parent(None, data.get("parent"))
        from .routing import department_head, employee_target, validate_member, calculate_deadline
        department = data.get('responsible_department')
        if department:
            head = department_head(department)
            validate_member(head, department, data.get('location'))
            if responsible_target and cls._resolve_one(responsible_target).pk != head.pk:
                raise TaskValidationError('Ответственный — руководитель выбранного подразделения.', code='task_department_responsible_invalid')
            responsible_target = employee_target(head)
            data['responsible_employee'] = head
            if executor_target:
                executor = cls._resolve_one(executor_target)
                validate_member(executor, department, data.get('location'))
                data['executor_employee'] = executor
            if not actor_user.is_superuser:
                from employees.assignment_targets import assignment_visibility
                visible = assignment_visibility(actor_user)[0]
                if not visible.filter(pk=head.pk).exists() or (executor_target and not visible.filter(pk=data['executor_employee'].pk).exists()) or not PermissionService.has_permission(employee=actor, permission='org_unit.view', obj=department):
                    raise TaskBusinessError('Подразделение или сотрудник недоступны.', code='task_permission_denied')
            if data.get('source_type') != 'project':
                data['due_at'] = calculate_deadline(data.get('priority', 'normal'), timezone.now(), data.get('due_at'))
                data['deadline_is_manual'] = data.get('priority') == 'blocking'
        cls._validate_dates(data.get('planned_start_at'), data.get('due_at'))
        task = Task.objects.create(number=cls._next_number(), title=title, description=description, author=author, responsible_target=responsible_target, executor_target=executor_target, created_by=actor_user, updated_by=actor_user, **data)
        if department and task.source_type != 'project':
            task.due_at = calculate_deadline(task.priority, task.created_at, task.due_at)
            task.save(update_fields=['due_at'])
        TaskStatusHistory.objects.create(task=task, to_status=TaskStatus.DRAFT, actor=actor)
        cls._record(task, actor, actor_user, "task.created", new={"status": task.status}, correlation_id=correlation_id)
        return task

    @classmethod
    @transaction.atomic
    def update(cls, *, task, actor, actor_user, version, correlation_id=None, **changes):
        task = cls._locked(task, version)
        cls._authorize(actor=actor, actor_user=actor_user, permission="task.edit", task=task)
        from .acceptance import validate_policy_change
        if 'acceptance_policy' in changes:
            validate_policy_change(task, changes['acceptance_policy'])
            if changes['acceptance_policy'] == task.acceptance_policy:
                changes.pop('acceptance_policy')
        if not changes:
            return task
        from organizations.object_services import require_available_location
        if "location" in changes and changes["location"] != task.location:
            require_available_location(changes["location"], actor_user)
        allowed = {"title", "description", "priority", "planned_start_at", "parent", "org_unit", "legal_entity", "location", "acceptance_policy", "completion_policy", "responsible_department"}
        if set(changes) - allowed:
            raise TaskValidationError("Попытка изменить защищённые поля задачи.", code="task_field_read_only")
        if task.status in {TaskStatus.COMPLETED, TaskStatus.CANCELLED}:
            raise TaskValidationError("Финальную задачу нельзя редактировать обычной командой.")
        cls._validate_dates(changes.get("planned_start_at", task.planned_start_at), task.due_at)
        cls._validate_parent(task, changes.get("parent", task.parent))
        old = {field: str(getattr(task, field)) for field in changes}
        from .routing import project_for, calculate_deadline, department_head, employee_target, validate_member
        project = project_for(task)
        if project and 'priority' in changes:
            raise TaskValidationError('У проектной задачи нет активного приоритета.', code='task_project_priority_disabled')
        if 'responsible_department' in changes:
            cls._authorize(actor=actor, actor_user=actor_user, permission='task.reassign', task=task)
            if not cls._assignment_administrator(actor, actor_user, task):
                raise TaskBusinessError('Ответственное подразделение меняет уполномоченный администратор.', code='task_permission_denied')
            department = changes['responsible_department']
            if not department:
                raise TaskValidationError('Укажите ответственное подразделение.')
            head = department_head(department)
            if not actor_user.is_superuser:
                from employees.assignment_targets import assignment_visibility
                if not assignment_visibility(actor_user)[0].filter(pk=head.pk).exists() or not PermissionService.has_permission(employee=actor, permission='org_unit.view', obj=department):
                    raise TaskBusinessError('Подразделение или руководитель недоступны.', code='task_permission_denied')
            validate_member(head, department, changes.get('location', task.location))
            if task.executor_employee:
                validate_member(task.executor_employee, department, changes.get('location', task.location))
            target = employee_target(head)
            TaskAssignmentHistory.objects.create(task=task, assignment_type='responsible', old_target=task.responsible_target, old_employee=task.responsible_employee, new_target=target, new_employee=head, changed_by=actor, reason='Изменение ответственного подразделения')
            changes.update(responsible_target=target, responsible_employee=head)
        if 'location' in changes and task.responsible_department:
            for member in (task.responsible_employee, task.executor_employee):
                if member:
                    validate_member(member, changes.get('responsible_department', task.responsible_department), changes['location'])
        if 'priority' in changes and changes['priority'] != task.priority:
            cls._authorize(actor=actor, actor_user=actor_user, permission='task.change_deadline', task=task)
            if changes['priority'] == 'blocking' and not task.deadline_is_manual:
                raise TaskValidationError('Сначала задайте явный дедлайн с причиной.', code='task_blocking_deadline_required')
            new_due = calculate_deadline(changes['priority'], task.created_at, task.due_at)
            TaskDeadlineHistory.objects.create(task=task, old_due_at=task.due_at, new_due_at=new_due, changed_by=actor, reason='Пересчёт приоритета от создания')
            changes['due_at'] = new_due
            changes['deadline_is_manual'] = changes['priority'] == 'blocking'
        cls._validate_dates(changes.get('planned_start_at', task.planned_start_at), changes.get('due_at', task.due_at))
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
            raise TaskValidationError('Для публикации нужны название, автор и ответственный.', code='task_publish_invalid')
        resolved = cls._resolve_one(task.responsible_target)
        from .routing import department_head, validate_member
        if not task.responsible_department:
            raise TaskValidationError('Администратор должен явно заполнить подразделение старой задачи.', code='task_department_required')
        if task.responsible_department:
            head = department_head(task.responsible_department)
            if resolved.pk != head.pk:
                raise TaskValidationError('Проверьте руководителя подразделения.', code='task_department_responsible_invalid')
            validate_member(head, task.responsible_department, task.location)
            if task.executor_target:
                validate_member(cls._resolve_one(task.executor_target), task.responsible_department, task.location)
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
        if not task.responsible_employee_id:
            raise TaskValidationError('До начала работы определите ответственного руководителя.')
        from .routing import department_head, validate_member
        if not task.responsible_department or department_head(task.responsible_department).pk != task.responsible_employee_id:
            raise TaskValidationError('До начала работы заполните подразделение и его ответственного руководителя.', code='task_department_required')
        validate_member(task.responsible_employee, task.responsible_department, task.location)
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
        from projects.models import Project, ProjectStatus, ProjectTaskLink
        from projects.services import ProjectService, project_lock
        original_project_id = ProjectTaskLink.objects.filter(task_id=task.pk,is_active=True).values_list("project_id", flat=True).first()
        if original_project_id:
            project_lock(original_project_id)
        task = cls._locked(task, version)
        cls._authorize(actor=actor, actor_user=actor_user, permission="task.reopen", task=task)
        current_project_id = ProjectTaskLink.objects.filter(task_id=task.pk,is_active=True).values_list("project_id", flat=True).first()
        if current_project_id != original_project_id:
            raise TaskValidationError("Связь задачи с проектом изменилась; повторите операцию.", code="task_project_link_changed")
        project = Project.objects.select_for_update().get(pk=current_project_id) if current_project_id else None
        if project and (project.is_archived or project.status == ProjectStatus.CANCELLED):
            raise TaskValidationError("Архивный или отменённый проект сначала нужно явно восстановить.", code="task_project_reopen_blocked")
        old = cls._transition(task, TaskStatus.IN_PROGRESS, actor, reason)
        previous_completed_at = task.completed_at
        task.completed_at = None
        task.updated_by = actor_user
        task.save(update_fields=["status", "completed_at", "version", "updated_by", "updated_at"])
        cls._record(task, actor, actor_user, "task.reopened", old={"status": old, "completed_at": previous_completed_at}, new={"status": task.status}, correlation_id=correlation_id, reason=reason)
        if project and project.status == ProjectStatus.COMPLETED:
            previous_project_end = project.actual_end_at
            project.status = ProjectStatus.ACTIVE
            project.actual_end_at = None
            project.version += 1
            project.updated_by = actor_user
            project.save(update_fields=["status", "actual_end_at", "version", "updated_by", "updated_at"])
            AuditService.record(action="project.reopened_by_task", entity=project, actor_user=actor_user,
                actor_employee=actor, old_value={"status":ProjectStatus.COMPLETED,"actual_end_at":previous_project_end},
                new_value={"status":project.status,"reason":reason[:500]}, correlation_id=correlation_id)
            DomainEventService.publish(event_type="project.reopened_by_task", entity=project, actor=actor_user,
                payload={"project_id":str(project.pk),"task_id":str(task.pk)}, correlation_id=correlation_id)
            if project.manager_id:
                DomainEventService.publish(event_type="notification.requested", entity=project, actor=actor_user,
                    payload={"reason":"PROJECT_TASK_REOPENED","recipient_employee_id":str(project.manager_id),
                             "project_id":str(project.pk),"project_number":project.number}, correlation_id=correlation_id)
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
        from .routing import project_for, validate_project_deadline
        project = project_for(task)
        if project:
            validate_project_deadline(project, new_due_at)
            task.deadline_from_project = new_due_at is None
            new_due_at = new_due_at or project.planned_end_at
        cls._authorize(actor=actor, actor_user=actor_user, permission="task.change_deadline", task=task)
        if not project and task.priority == 'blocking' and not new_due_at:
            raise TaskValidationError('Блокирующей задаче нужен явный дедлайн.', code='task_blocking_deadline_required')
        cls._validate_dates(task.planned_start_at, new_due_at)
        requires_reason = True
        if requires_reason and not reason.strip():
            raise TaskValidationError("Для изменения срока обязательна причина.", code="task_deadline_reason_required")
        if task.status in {TaskStatus.COMPLETED, TaskStatus.CANCELLED}:
            raise TaskValidationError("Срок финальной задачи изменить нельзя.", code="task_deadline_invalid")
        old_due = task.due_at
        task.due_at = new_due_at
        task.deadline_is_manual = not task.deadline_from_project and new_due_at is not None
        task.version += 1
        task.updated_by = actor_user
        task.save(update_fields=["due_at", "deadline_from_project", "deadline_is_manual", "version", "updated_by", "updated_at"])
        TaskDeadlineHistory.objects.create(task=task, old_due_at=old_due, new_due_at=new_due_at, changed_by=actor, reason=reason)
        cls._record(task, actor, actor_user, "task.deadline_changed", old={"due_at": old_due}, new={"due_at": new_due_at}, correlation_id=correlation_id, old_due_at=old_due, new_due_at=new_due_at, reason=reason)
        return task

    @classmethod
    @transaction.atomic
    def reassign(cls, *, task, actor, actor_user, version, assignment_type, new_target, reason="", correlation_id=None):
        task = cls._locked(task, version)
        cls._authorize(actor=actor, actor_user=actor_user, permission="task.reassign", task=task)
        if not task.responsible_department:
            raise TaskValidationError('Перед переназначением администратор должен заполнить подразделение.', code='task_department_required')
        if task.status in {TaskStatus.COMPLETED, TaskStatus.CANCELLED}:
            raise TaskValidationError("Финальную задачу нельзя переназначить.", code="task_assignment_invalid")
        requires_reason = task.status in {TaskStatus.IN_PROGRESS, TaskStatus.WAITING, TaskStatus.REVIEW} or task.is_overdue
        if requires_reason and not reason.strip():
            raise TaskValidationError("Для переназначения обязательна причина.", code="task_reassign_reason_required")
        if assignment_type not in TaskAssignmentHistory.Type.values:
            raise TaskValidationError("Неизвестный тип назначения.", code="task_assignment_invalid")
        new_employee = cls._resolve_one(new_target)
        from .routing import department_head, validate_member
        if task.responsible_department:
            validate_member(new_employee, task.responsible_department, task.location)
            if assignment_type == 'responsible' and new_employee.pk != department_head(task.responsible_department).pk:
                raise TaskValidationError('Ответственный — руководитель подразделения.', code='task_department_responsible_invalid')
            administrative = cls._assignment_administrator(actor, actor_user, task)
            if not actor_user.is_superuser and actor.pk != task.responsible_employee_id and not administrative:
                raise TaskBusinessError('Исполнителя назначает ответственный руководитель или уполномоченный администратор.', code='task_permission_denied')
            if not actor_user.is_superuser:
                from employees.assignment_targets import assignment_visibility
                if not assignment_visibility(actor_user)[0].filter(pk=new_employee.pk).exists():
                    raise TaskBusinessError('Сотрудник недоступен.', code='task_permission_denied')
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
