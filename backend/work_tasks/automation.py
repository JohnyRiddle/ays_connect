from __future__ import annotations

import logging
from datetime import timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dateutil.rrule import rrulestr
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from audit.services import AuditService
from events.services import DomainEventService
from .exceptions import TaskBusinessError, TaskValidationError
from .models import (
    DeadlineRule, SourceType, TaskChecklist, TaskChecklistItem, TaskOccurrence,
    TaskRecurrenceRule, TaskSavedView, TaskTemplate, TaskTemplateChecklist,
)
from .policies import TaskAccessPolicy
from .services import TaskService

logger = logging.getLogger(__name__)


class TemplatePermissionMixin:
    @staticmethod
    def authorize(actor, actor_user, permission):
        if actor_user and actor_user.is_superuser:
            return
        if not TaskAccessPolicy.allows(employee=actor, permission=permission):
            raise TaskBusinessError("Недостаточно прав.", code="task_permission_denied")


class TaskTemplateService(TemplatePermissionMixin):
    @staticmethod
    def _record(template, actor, actor_user, action, correlation_id=None, payload=None):
        AuditService.record(action=action, entity=template, actor_user=actor_user, actor_employee=actor, correlation_id=correlation_id)
        DomainEventService.publish(event_type=action.replace("task_template.", "task.template."), entity=template, actor=actor_user, payload={"template_id": str(template.pk), "actor_id": str(actor.pk), **(payload or {})}, correlation_id=correlation_id)

    @staticmethod
    def _validate_rule(deadline_rule, deadline_offset):
        if deadline_rule == DeadlineRule.NONE and deadline_offset:
            raise TaskValidationError("Для NONE нельзя задавать deadline offset.", code="task_template_deadline_invalid")
        if deadline_rule != DeadlineRule.NONE and (not deadline_offset or deadline_offset.total_seconds() <= 0):
            raise TaskValidationError("Для deadline rule нужен положительный offset.", code="task_template_deadline_invalid")

    @classmethod
    @transaction.atomic
    def create(cls, *, actor, actor_user, checklist_templates=(), correlation_id=None, **data):
        cls.authorize(actor, actor_user, "task_template.manage")
        cls._validate_rule(data.get("deadline_rule", DeadlineRule.NONE), data.get("deadline_offset"))
        template = TaskTemplate.objects.create(created_by=actor, **data)
        for index, checklist in enumerate(checklist_templates, start=1):
            TaskTemplateChecklist.objects.create(task_template=template, checklist_template=checklist, position=index)
        cls._record(template, actor, actor_user, "task_template.created", correlation_id)
        return template

    @classmethod
    @transaction.atomic
    def update(cls, *, template, actor, actor_user, checklist_templates=None, correlation_id=None, **changes):
        cls.authorize(actor, actor_user, "task_template.manage")
        rule = changes.get("deadline_rule", template.deadline_rule)
        offset = changes.get("deadline_offset", template.deadline_offset)
        cls._validate_rule(rule, offset)
        for field, value in changes.items(): setattr(template, field, value)
        template.save()
        if checklist_templates is not None:
            template.checklist_links.all().delete()
            for index, checklist in enumerate(checklist_templates, start=1):
                TaskTemplateChecklist.objects.create(task_template=template, checklist_template=checklist, position=index)
        cls._record(template, actor, actor_user, "task_template.updated", correlation_id)
        return template

    @classmethod
    @transaction.atomic
    def deactivate(cls, *, template, actor, actor_user, correlation_id=None):
        cls.authorize(actor, actor_user, "task_template.manage")
        template.is_active = False
        template.save(update_fields=["is_active", "updated_at"])
        template.recurrence_rules.filter(is_active=True).update(is_active=False, next_occurrence_at=None)
        cls._record(template, actor, actor_user, "task_template.deactivated", correlation_id)
        return template

    @staticmethod
    def _dates(template, occurrence_at=None, planned_start_at=None):
        now = timezone.now()
        reference = occurrence_at or now
        planned = occurrence_at or planned_start_at
        if planned is None and template.planned_start_offset:
            planned = reference + template.planned_start_offset
        if template.deadline_rule == DeadlineRule.NONE:
            due = None
        elif template.deadline_rule == DeadlineRule.AFTER_CREATION:
            due = reference + template.deadline_offset
        else:
            if planned is None:
                raise TaskValidationError("Deadline AFTER_PLANNED_START требует плановую дату.", code="task_template_deadline_invalid")
            due = planned + template.deadline_offset
        return planned, due

    @classmethod
    @transaction.atomic
    def create_task(cls, *, template, actor, actor_user, create_and_publish=False, occurrence_at=None, recurrence_rule=None, correlation_id=None):
        cls.authorize(actor, actor_user, "task_template.use")
        template = TaskTemplate.objects.select_for_update().get(pk=template.pk)
        if not template.is_active:
            raise TaskValidationError("Шаблон деактивирован.", code="task_template_inactive")
        responsible = TaskService._resolve_one(template.responsible_target)
        executor = TaskService._resolve_one(template.executor_target, required=False)
        planned, due = cls._dates(template, occurrence_at=occurrence_at)
        source_type = SourceType.RECURRENCE if recurrence_rule else SourceType.TEMPLATE
        task = TaskService.create(
            actor=actor, actor_user=actor_user, title=template.task_title,
            description=template.task_description, responsible_target=template.responsible_target,
            executor_target=template.executor_target, responsible_employee=responsible,
            executor_employee=executor, priority=template.default_priority,
            acceptance_policy=template.acceptance_policy, completion_policy=template.completion_policy,
            planned_start_at=planned, due_at=due, org_unit=template.org_unit,
            legal_entity=template.legal_entity, location=template.location,
            source_type=source_type, source_template=template, recurrence_rule=recurrence_rule,
            correlation_id=correlation_id,
        )
        for link in template.checklist_links.select_related("checklist_template").prefetch_related("checklist_template__items").order_by("position"):
            source = link.checklist_template
            checklist = TaskChecklist.objects.create(task=task, name=source.name, source_template=source, created_by=actor)
            TaskChecklistItem.objects.bulk_create([TaskChecklistItem(checklist=checklist, text=item.text, position=item.position, required=item.required) for item in source.items.all()])
        if create_and_publish:
            task = TaskService.publish(task=task, actor=actor, actor_user=actor_user, version=task.version, correlation_id=correlation_id)
        DomainEventService.publish(event_type="task.template_instantiated", entity=task, actor=actor_user, payload={"task_id": str(task.pk), "task_number": task.number, "template_id": str(template.pk)}, correlation_id=correlation_id)
        return task


class RecurrenceService(TemplatePermissionMixin):
    SUPPORTED_FREQS = {"HOURLY", "DAILY", "WEEKLY", "MONTHLY", "YEARLY"}

    @classmethod
    def parse(cls, rrule_text, starts_at, timezone_name):
        try:
            zone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise TaskValidationError("Неизвестная timezone.", code="task_recurrence_timezone_invalid") from exc
        normalized = rrule_text.strip().removeprefix("RRULE:")
        parts = dict(part.split("=", 1) for part in normalized.split(";") if "=" in part)
        if parts.get("FREQ") not in cls.SUPPORTED_FREQS:
            raise TaskValidationError("Неподдерживаемая частота RRULE.", code="task_recurrence_rrule_invalid")
        try:
            interval = int(parts.get("INTERVAL", "1"))
        except ValueError as exc:
            raise TaskValidationError("Некорректный RRULE INTERVAL.", code="task_recurrence_rrule_invalid") from exc
        if interval <= 0:
            raise TaskValidationError("RRULE INTERVAL должен быть положительным.", code="task_recurrence_rrule_invalid")
        try:
            rule = rrulestr(normalized, dtstart=starts_at.astimezone(zone))
            rule.after(starts_at.astimezone(zone), inc=True)
        except Exception as exc:
            raise TaskValidationError("Некорректный RRULE.", code="task_recurrence_rrule_invalid") from exc
        return normalized, rule, zone

    @classmethod
    @transaction.atomic
    def create(cls, *, actor, actor_user, name, task_template, rrule, timezone_name, starts_at, ends_at=None, correlation_id=None):
        cls.authorize(actor, actor_user, "task_recurrence.manage")
        normalized, parsed, zone = cls.parse(rrule, starts_at, timezone_name)
        if ends_at and ends_at < starts_at:
            raise TaskValidationError("ends_at раньше starts_at.", code="task_recurrence_range_invalid")
        next_at = parsed.after(timezone.now().astimezone(zone), inc=True)
        if ends_at and next_at and next_at > ends_at: next_at = None
        rule = TaskRecurrenceRule.objects.create(name=name, task_template=task_template, rrule=normalized, timezone=timezone_name, starts_at=starts_at, ends_at=ends_at, next_occurrence_at=next_at, created_by=actor)
        cls._record(rule, actor, actor_user, "task_recurrence.created", correlation_id)
        return rule

    @staticmethod
    def _record(rule, actor, actor_user, action, correlation_id=None, payload=None):
        AuditService.record(action=action, entity=rule, actor_user=actor_user, actor_employee=actor, correlation_id=correlation_id)
        DomainEventService.publish(event_type=action.replace("task_recurrence.", "task.recurrence."), entity=rule, actor=actor_user, payload={"recurrence_rule_id": str(rule.pk), "actor_id": str(actor.pk), **(payload or {})}, correlation_id=correlation_id)

    @classmethod
    @transaction.atomic
    def update(cls, *, rule, actor, actor_user, correlation_id=None, **changes):
        cls.authorize(actor, actor_user, "task_recurrence.manage")
        candidate_rrule = changes.get("rrule", rule.rrule)
        candidate_tz = changes.get("timezone", rule.timezone)
        candidate_start = changes.get("starts_at", rule.starts_at)
        normalized, parsed, zone = cls.parse(candidate_rrule, candidate_start, candidate_tz)
        changes["rrule"] = normalized
        for field, value in changes.items(): setattr(rule, field, value)
        rule.next_occurrence_at = parsed.after(timezone.now().astimezone(zone), inc=True) if rule.is_active else None
        rule.save()
        cls._record(rule, actor, actor_user, "task_recurrence.updated", correlation_id)
        return rule

    @classmethod
    @transaction.atomic
    def pause(cls, *, rule, actor, actor_user, correlation_id=None):
        cls.authorize(actor, actor_user, "task_recurrence.manage")
        rule.is_active, rule.next_occurrence_at = False, None
        rule.save(update_fields=["is_active", "next_occurrence_at", "updated_at"])
        cls._record(rule, actor, actor_user, "task_recurrence.paused", correlation_id)
        return rule

    @classmethod
    @transaction.atomic
    def resume(cls, *, rule, actor, actor_user, correlation_id=None):
        cls.authorize(actor, actor_user, "task_recurrence.manage")
        _, parsed, zone = cls.parse(rule.rrule, rule.starts_at, rule.timezone)
        rule.is_active = True
        rule.next_occurrence_at = parsed.after(timezone.now().astimezone(zone), inc=True)
        rule.save(update_fields=["is_active", "next_occurrence_at", "updated_at"])
        cls._record(rule, actor, actor_user, "task_recurrence.resumed", correlation_id)
        return rule

    @classmethod
    def _process_occurrence(cls, occurrence):
        with transaction.atomic():
            # Lock only the occurrence row. Joining nullable creator/user fields
            # makes PostgreSQL reject SELECT FOR UPDATE on the outer join.
            occurrence = TaskOccurrence.objects.select_for_update().get(pk=occurrence.pk)
            if occurrence.status == TaskOccurrence.Status.GENERATED:
                return occurrence
            if occurrence.status == TaskOccurrence.Status.SKIPPED:
                return occurrence
            occurrence.attempts += 1
            occurrence.save(update_fields=["attempts"])
            rule = occurrence.recurrence_rule
            actor, actor_user = rule.created_by, rule.created_by.user
            task = TaskTemplateService.create_task(template=rule.task_template, actor=actor, actor_user=actor_user, create_and_publish=True, occurrence_at=occurrence.occurrence_at, recurrence_rule=rule)
            occurrence.task, occurrence.status = task, TaskOccurrence.Status.GENERATED
            occurrence.processed_at, occurrence.last_error = timezone.now(), ""
            occurrence.save(update_fields=["task", "status", "processed_at", "last_error"])
            rule.last_generated_at, rule.last_error = timezone.now(), ""
            rule.save(update_fields=["last_generated_at", "last_error", "updated_at"])
            AuditService.record(action="task_occurrence.generated", entity=occurrence, actor_user=actor_user, actor_employee=actor)
            DomainEventService.publish(event_type="task.occurrence.generated", entity=occurrence, actor=actor_user, payload={"occurrence_id": str(occurrence.pk), "task_id": str(task.pk), "recurrence_rule_id": str(rule.pk)})
            return occurrence

    @classmethod
    def process_occurrence(cls, occurrence):
        try:
            return cls._process_occurrence(occurrence)
        except Exception as exc:
            message = getattr(exc, "default_detail", None) or str(exc) or exc.__class__.__name__
            message = str(message)[:1000]
            with transaction.atomic():
                locked = TaskOccurrence.objects.select_for_update().get(pk=occurrence.pk)
                locked.status, locked.last_error, locked.processed_at = TaskOccurrence.Status.FAILED, message, timezone.now()
                locked.attempts = max(locked.attempts, 1)
                locked.save(update_fields=["status", "last_error", "processed_at", "attempts"])
                rule = locked.recurrence_rule
                rule.last_error = message
                rule.save(update_fields=["last_error", "updated_at"])
                AuditService.record(action="task_occurrence.failed", entity=locked)
                DomainEventService.publish(event_type="task.occurrence.failed", entity=locked, payload={"occurrence_id": str(locked.pk), "recurrence_rule_id": str(rule.pk), "error": message})
            return locked

    @classmethod
    def generate_due_occurrences(cls, *, now=None, horizon=None):
        now = now or timezone.now()
        horizon = horizon or now + timedelta(hours=settings.TASK_RECURRENCE_HORIZON_HOURS)
        total = 0
        rules = TaskRecurrenceRule.objects.filter(is_active=True, task_template__is_active=True).order_by("pk")
        for rule in rules:
            if total >= settings.TASK_MAX_TOTAL_OCCURRENCES_PER_RUN: break
            _, parsed, zone = cls.parse(rule.rrule, rule.starts_at, rule.timezone)
            start = max(now, rule.starts_at)
            end = min(horizon, rule.ends_at) if rule.ends_at else horizon
            candidates = parsed.between(start.astimezone(zone), end.astimezone(zone), inc=True)
            limit = min(settings.TASK_MAX_OCCURRENCES_PER_RULE_PER_RUN, settings.TASK_MAX_TOTAL_OCCURRENCES_PER_RUN - total)
            for occurrence_at in candidates[:limit]:
                occurrence, _ = TaskOccurrence.objects.get_or_create(recurrence_rule=rule, occurrence_at=occurrence_at)
                if occurrence.status == TaskOccurrence.Status.PENDING:
                    cls.process_occurrence(occurrence)
                total += 1
            next_at = parsed.after(end.astimezone(zone), inc=False)
            rule.next_occurrence_at = next_at if not rule.ends_at or (next_at and next_at <= rule.ends_at) else None
            rule.save(update_fields=["next_occurrence_at", "updated_at"])
        return total

    @classmethod
    def retry_occurrence(cls, *, occurrence, actor, actor_user):
        cls.authorize(actor, actor_user, "task_recurrence.run")
        if occurrence.status != TaskOccurrence.Status.FAILED:
            raise TaskValidationError("Повторить можно только FAILED occurrence.", code="task_occurrence_retry_invalid")
        AuditService.record(action="task_occurrence.retried", entity=occurrence, actor_user=actor_user, actor_employee=actor)
        return cls.process_occurrence(occurrence)

    @classmethod
    @transaction.atomic
    def skip_occurrence(cls, *, occurrence, actor, actor_user, reason):
        cls.authorize(actor, actor_user, "task_recurrence.manage")
        occurrence = TaskOccurrence.objects.select_for_update().get(pk=occurrence.pk)
        if occurrence.status == TaskOccurrence.Status.GENERATED:
            raise TaskValidationError("Созданный occurrence пропустить нельзя.", code="task_occurrence_skip_invalid")
        occurrence.status, occurrence.skipped_by, occurrence.skip_reason, occurrence.processed_at = TaskOccurrence.Status.SKIPPED, actor, reason.strip(), timezone.now()
        occurrence.save(update_fields=["status", "skipped_by", "skip_reason", "processed_at"])
        AuditService.record(action="task_occurrence.skipped", entity=occurrence, actor_user=actor_user, actor_employee=actor)
        DomainEventService.publish(event_type="task.occurrence.skipped", entity=occurrence, actor=actor_user, payload={"occurrence_id": str(occurrence.pk), "reason": occurrence.skip_reason})
        return occurrence
