import uuid

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .exceptions import TaskBusinessError, TaskValidationError
from .models import TaskPriority, TaskSavedView, TaskStatus
from .policies import TaskAccessPolicy
from .selectors import TaskSelector
from .state_machine import TaskStateMachine


class SavedViewValidator:
    UUID_FIELDS = {"author", "responsible_employee", "executor_employee", "org_unit", "legal_entity", "location", "parent"}
    DATE_FIELDS = {"created_from", "created_to", "due_from", "due_to"}
    ALLOWED = {"status", "priority", "overdue", "search", *UUID_FIELDS, *DATE_FIELDS}
    ORDERINGS = {"created_at", "updated_at", "due_at", "priority", "number"}

    @classmethod
    def validate_filters(cls, filters):
        if not isinstance(filters, dict) or set(filters) - cls.ALLOWED:
            raise TaskValidationError("Saved View содержит неизвестные фильтры.", code="task_saved_view_invalid")
        clean = {}
        for key, value in filters.items():
            if key == "status" and value not in TaskStatus.values: raise TaskValidationError("Некорректный status.", code="task_saved_view_invalid")
            if key == "priority" and value not in TaskPriority.values: raise TaskValidationError("Некорректный priority.", code="task_saved_view_invalid")
            if key in cls.UUID_FIELDS:
                try: uuid.UUID(str(value))
                except (ValueError, TypeError): raise TaskValidationError(f"Некорректный UUID: {key}.", code="task_saved_view_invalid")
            if key in cls.DATE_FIELDS and not parse_datetime(str(value)):
                raise TaskValidationError(f"Некорректная дата: {key}.", code="task_saved_view_invalid")
            if key == "overdue" and value not in (True, False, "true", "false"):
                raise TaskValidationError("Некорректный overdue.", code="task_saved_view_invalid")
            clean[key] = value
        return clean

    @classmethod
    def validate_ordering(cls, ordering):
        if ordering.lstrip("-") not in cls.ORDERINGS:
            raise TaskValidationError("Некорректная сортировка Saved View.", code="task_saved_view_invalid")
        return ordering


class SavedViewService:
    @staticmethod
    @transaction.atomic
    def create(*, owner, name, filters, ordering="-created_at", is_default=False):
        filters = SavedViewValidator.validate_filters(filters)
        ordering = SavedViewValidator.validate_ordering(ordering)
        if is_default: TaskSavedView.objects.filter(owner=owner, is_active=True, is_default=True).update(is_default=False)
        return TaskSavedView.objects.create(owner=owner, name=name.strip(), filters=filters, ordering=ordering, is_default=is_default)

    @staticmethod
    @transaction.atomic
    def update(*, view, owner, **changes):
        if view.owner_id != owner.pk: raise TaskBusinessError("Saved View недоступен.", code="task_saved_view_forbidden")
        if "filters" in changes: changes["filters"] = SavedViewValidator.validate_filters(changes["filters"])
        if "ordering" in changes: changes["ordering"] = SavedViewValidator.validate_ordering(changes["ordering"])
        if changes.get("is_default"): TaskSavedView.objects.filter(owner=owner, is_active=True, is_default=True).exclude(pk=view.pk).update(is_default=False)
        for field, value in changes.items(): setattr(view, field, value)
        view.save()
        return view

    @staticmethod
    @transaction.atomic
    def deactivate(*, view, owner):
        if view.owner_id != owner.pk: raise TaskBusinessError("Saved View недоступен.", code="task_saved_view_forbidden")
        view.is_active, view.is_default = False, False
        view.save(update_fields=["is_active", "is_default", "updated_at"])
        return view


class SystemViewService:
    VALUES = {"my_tasks", "created_by_me", "watching", "overdue", "completed", "without_deadline"}

    @classmethod
    def apply(cls, queryset, employee, code):
        code = code.lower()
        if code not in cls.VALUES: raise TaskValidationError("Неизвестное системное представление.", code="task_system_view_invalid")
        if code == "my_tasks": return queryset.filter(Q(responsible_employee=employee) | Q(executor_employee=employee)).distinct()
        if code == "created_by_me": return queryset.filter(author=employee)
        if code == "watching": return queryset.filter(watcher_records__employee=employee, watcher_records__removed_at__isnull=True).distinct()
        if code == "overdue": return queryset.filter(due_at__lt=timezone.now()).exclude(status__in=(TaskStatus.COMPLETED, TaskStatus.CANCELLED))
        if code == "completed": return queryset.filter(status=TaskStatus.COMPLETED)
        return queryset.filter(due_at__isnull=True)


class TaskUXService:
    ACTIONS = {
        "edit": "task.edit", "publish": "task.assign", "start": "task.start",
        "pause": "task.pause", "resume": "task.pause", "complete": "task.complete",
        "accept": "task.accept", "reject": "task.reject", "reopen": "task.reopen",
        "cancel": "task.cancel", "reassign": "task.reassign",
        "change_deadline": "task.change_deadline", "comment": "task.comment", "watch": "task.watch",
    }
    TRANSITIONS = {
        "publish": TaskStatus.OPEN, "start": TaskStatus.IN_PROGRESS,
        "pause": TaskStatus.WAITING, "resume": TaskStatus.IN_PROGRESS,
        "complete": TaskStatus.COMPLETED, "accept": TaskStatus.COMPLETED,
        "reject": TaskStatus.IN_PROGRESS, "reopen": TaskStatus.IN_PROGRESS,
        "cancel": TaskStatus.CANCELLED,
    }

    @classmethod
    def available_actions(cls, task, employee, is_superuser=False):
        if not is_superuser and not TaskAccessPolicy.allows(employee=employee, permission="task.view", task=task):
            return []
        actions = []
        for action, permission in cls.ACTIONS.items():
            permitted = is_superuser or TaskAccessPolicy.allows(employee=employee, permission=permission, task=task)
            if not permitted: continue
            if action in {"edit", "reassign", "change_deadline"} and task.status in {TaskStatus.COMPLETED, TaskStatus.CANCELLED}: continue
            target = cls.TRANSITIONS.get(action)
            if target and target not in TaskStateMachine.ALLOWED.get(task.status, set()): continue
            if action == "accept" and task.status != TaskStatus.REVIEW: continue
            if action == "reject" and task.status != TaskStatus.REVIEW: continue
            if action in {"accept", "reject"}:
                expected = task.author_id if task.acceptance_policy == "author" else task.responsible_employee_id
                if employee.pk != expected: continue
            if action == "complete" and task.status != TaskStatus.IN_PROGRESS: continue
            if action == "complete" and task.production_checklists.filter(removed_at__isnull=True, items__required=True, items__is_completed=False).exists(): continue
            if action == "pause" and task.status != TaskStatus.IN_PROGRESS: continue
            if action == "resume" and task.status != TaskStatus.WAITING: continue
            actions.append(action)
        return actions

    @staticmethod
    def counters(employee, queryset=None):
        queryset = queryset if queryset is not None else TaskSelector.visible_to(employee)
        return queryset.aggregate(
            my_tasks=Count("id", filter=Q(responsible_employee=employee) | Q(executor_employee=employee), distinct=True),
            overdue=Count("id", filter=Q(due_at__lt=timezone.now()) & ~Q(status__in=(TaskStatus.COMPLETED, TaskStatus.CANCELLED)), distinct=True),
            waiting=Count("id", filter=Q(status=TaskStatus.WAITING), distinct=True),
            review=Count("id", filter=Q(status=TaskStatus.REVIEW), distinct=True),
            created_by_me=Count("id", filter=Q(author=employee), distinct=True),
            watching=Count("id", filter=Q(watcher_records__employee=employee, watcher_records__removed_at__isnull=True), distinct=True),
        )
