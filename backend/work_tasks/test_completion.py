from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from access_control.models import EmployeeRole, Permission, Role, RolePermission, Scope
from accounts.models import User
from audit.models import AuditEvent
from employees.models import AssignmentTarget, Employee
from events.models import OutboxEvent
from organizations.models import LegalEntity, OrgUnit
from .automation import RecurrenceService, TaskTemplateService
from .exceptions import TaskBusinessError, TaskValidationError
from .models import (
    ChecklistTemplate, ChecklistTemplateItem, DeadlineRule, SourceType, Task,
    TaskOccurrence, TaskPriority, TaskSavedView, TaskStatus, TaskWatcher,
)
from .services import TaskService
from .ux import SavedViewService, SavedViewValidator, SystemViewService, TaskUXService


class CompletionPhaseTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username="completion-admin", email="completion@test.local", password="pass")
        self.le = LegalEntity.objects.create(name="Completion LE")
        self.unit = OrgUnit.objects.create(name="Completion Unit", legal_entity=self.le)
        self.actor = Employee.objects.create(user=self.user, first_name="Автор", legal_entity=self.le, org_unit=self.unit)
        self.executor = Employee.objects.create(first_name="Исполнитель", legal_entity=self.le, org_unit=self.unit)
        self.target = AssignmentTarget.objects.create(target_type=AssignmentTarget.Type.EMPLOYEE, employee=self.executor)

    def template(self, **kwargs):
        data = {"name": "Template", "task_title": "From template", "responsible_target": self.target, "legal_entity": self.le, "org_unit": self.unit}
        data.update(kwargs)
        return TaskTemplateService.create(actor=self.actor, actor_user=self.user, **data)


class TaskTemplateTests(CompletionPhaseTestCase):
    def test_template_snapshot_deadline_checklist_and_publish(self):
        checklist = ChecklistTemplate.objects.create(name="Template checklist", created_by=self.actor)
        ChecklistTemplateItem.objects.create(template=checklist, text="Old item", position=1, required=True)
        template = self.template(default_priority=TaskPriority.NORMAL, deadline_rule=DeadlineRule.AFTER_CREATION, deadline_offset=timedelta(hours=4), checklist_templates=[checklist])
        before = timezone.now()
        first = TaskTemplateService.create_task(template=template, actor=self.actor, actor_user=self.user, create_and_publish=True)
        self.assertEqual(first.status, TaskStatus.OPEN)
        self.assertEqual(first.source_type, SourceType.TEMPLATE)
        self.assertEqual(first.source_template, template)
        self.assertEqual(first.responsible_employee, self.executor)
        self.assertGreaterEqual(first.due_at, before + timedelta(hours=4))
        self.assertEqual(first.production_checklists.get().items.get().text, "Old item")

        template.default_priority = TaskPriority.HIGH
        template.save(update_fields=["default_priority"])
        item = checklist.items.get(); item.text = "New item"; item.save(update_fields=["text"])
        second = TaskTemplateService.create_task(template=template, actor=self.actor, actor_user=self.user)
        first.refresh_from_db()
        self.assertEqual(first.priority, TaskPriority.NORMAL)
        self.assertEqual(first.production_checklists.get().items.get().text, "Old item")
        self.assertEqual(second.priority, TaskPriority.HIGH)
        self.assertEqual(second.production_checklists.get().items.get().text, "New item")

    def test_deadline_rules_and_deactivated_template(self):
        none = TaskTemplateService.create_task(template=self.template(deadline_rule=DeadlineRule.NONE), actor=self.actor, actor_user=self.user)
        self.assertIsNone(none.due_at)
        planned_template = self.template(name="Planned", deadline_rule=DeadlineRule.AFTER_PLANNED_START, deadline_offset=timedelta(hours=2), planned_start_offset=timedelta(hours=1))
        planned = TaskTemplateService.create_task(template=planned_template, actor=self.actor, actor_user=self.user)
        self.assertEqual(planned.due_at - planned.planned_start_at, timedelta(hours=2))
        TaskTemplateService.deactivate(template=planned_template, actor=self.actor, actor_user=self.user)
        with self.assertRaises(TaskValidationError):
            TaskTemplateService.create_task(template=planned_template, actor=self.actor, actor_user=self.user)

    def test_unresolved_assignment_rolls_back_task(self):
        self.executor.is_active = False; self.executor.save(update_fields=["is_active"])
        template = self.template()
        count = Task.objects.count()
        with self.assertRaises(TaskBusinessError):
            TaskTemplateService.create_task(template=template, actor=self.actor, actor_user=self.user)
        self.assertEqual(Task.objects.count(), count)

    def test_template_instantiation_rolls_back_task_audit_and_outbox(self):
        template = self.template()
        task_count = Task.objects.count()
        audit_count = AuditEvent.objects.count()
        outbox_count = OutboxEvent.objects.count()

        with patch(
            "work_tasks.services.DomainEventService.publish",
            side_effect=RuntimeError("outbox unavailable"),
        ):
            with self.assertRaises(RuntimeError):
                TaskTemplateService.create_task(
                    template=template, actor=self.actor, actor_user=self.user
                )

        self.assertEqual(Task.objects.count(), task_count)
        self.assertEqual(AuditEvent.objects.count(), audit_count)
        self.assertEqual(OutboxEvent.objects.count(), outbox_count)


class RecurrenceTests(CompletionPhaseTestCase):
    def test_rrule_validation_daily_weekly_monthly_and_timezone(self):
        starts = timezone.now()
        for rule in ("FREQ=DAILY", "FREQ=WEEKLY;BYDAY=MO,WE,FR", "FREQ=MONTHLY;BYMONTHDAY=1"):
            normalized, parsed, zone = RecurrenceService.parse(rule, starts, "Asia/Tokyo")
            self.assertTrue(parsed.after(starts.astimezone(zone), inc=True))
        with self.assertRaises(TaskValidationError): RecurrenceService.parse("FREQ=SECONDLY", starts, "UTC")
        with self.assertRaises(TaskValidationError): RecurrenceService.parse("FREQ=DAILY", starts, "Invalid/Zone")

    def test_generation_is_idempotent_and_preserves_provenance(self):
        starts = timezone.now().replace(microsecond=0)
        template = self.template(deadline_rule=DeadlineRule.AFTER_CREATION, deadline_offset=timedelta(hours=1))
        rule = RecurrenceService.create(actor=self.actor, actor_user=self.user, name="Daily", task_template=template, rrule="FREQ=DAILY", timezone_name="Asia/Novosibirsk", starts_at=starts)
        RecurrenceService.generate_due_occurrences(now=starts, horizon=starts + timedelta(minutes=1))
        RecurrenceService.generate_due_occurrences(now=starts, horizon=starts + timedelta(minutes=1))
        self.assertEqual(rule.occurrences.count(), 1)
        occurrence = rule.occurrences.get()
        self.assertEqual(occurrence.status, TaskOccurrence.Status.GENERATED, occurrence.last_error)
        self.assertEqual(Task.objects.filter(recurrence_rule=rule).count(), 1)
        self.assertEqual(occurrence.task.source_type, SourceType.RECURRENCE)

    def test_failed_occurrence_retry_after_assignment_fix(self):
        starts = timezone.now().replace(microsecond=0)
        self.executor.is_active = False; self.executor.save(update_fields=["is_active"])
        template = self.template()
        rule = RecurrenceService.create(actor=self.actor, actor_user=self.user, name="Failure", task_template=template, rrule="FREQ=DAILY", timezone_name="UTC", starts_at=starts)
        occurrence = TaskOccurrence.objects.create(recurrence_rule=rule, occurrence_at=starts)
        occurrence = RecurrenceService.process_occurrence(occurrence)
        self.assertEqual(occurrence.status, TaskOccurrence.Status.FAILED)
        self.assertFalse(occurrence.task_id)
        self.executor.is_active = True; self.executor.save(update_fields=["is_active"])
        occurrence = RecurrenceService.retry_occurrence(occurrence=occurrence, actor=self.actor, actor_user=self.user)
        self.assertEqual(occurrence.status, TaskOccurrence.Status.GENERATED, occurrence.last_error)
        self.assertEqual(Task.objects.filter(recurrence_rule=rule).count(), 1)

    def test_pause_resume_skips_paused_period_and_runaway_limit(self):
        starts = timezone.now().replace(microsecond=0) - timedelta(days=10)
        rule = RecurrenceService.create(actor=self.actor, actor_user=self.user, name="Paused", task_template=self.template(), rrule="FREQ=HOURLY", timezone_name="UTC", starts_at=starts)
        RecurrenceService.pause(rule=rule, actor=self.actor, actor_user=self.user)
        self.assertEqual(RecurrenceService.generate_due_occurrences(now=timezone.now(), horizon=timezone.now() + timedelta(hours=2)), 0)
        rule = RecurrenceService.resume(rule=rule, actor=self.actor, actor_user=self.user)
        self.assertGreaterEqual(rule.next_occurrence_at, timezone.now() - timedelta(seconds=1))
        with override_settings(TASK_MAX_OCCURRENCES_PER_RULE_PER_RUN=2, TASK_MAX_TOTAL_OCCURRENCES_PER_RUN=2):
            count = RecurrenceService.generate_due_occurrences(now=timezone.now(), horizon=timezone.now() + timedelta(hours=5))
        self.assertLessEqual(count, 2)


class SavedViewsAndUXTests(CompletionPhaseTestCase):
    def setUp(self):
        super().setUp()
        self.mine = Task.objects.create(number="TASK-910001", title="Mine", author=self.actor, responsible_target=self.target, responsible_employee=self.actor, created_by=self.user, updated_by=self.user)
        self.watched = Task.objects.create(number="TASK-910002", title="Watched", author=self.executor, responsible_target=self.target, responsible_employee=self.executor, created_by=self.user, updated_by=self.user)
        TaskWatcher.objects.create(task=self.watched, employee=self.actor, added_by=self.actor)

    def test_saved_view_validation_default_and_ownership(self):
        first = SavedViewService.create(owner=self.actor, name="First", filters={"status": "draft"}, is_default=True)
        second = SavedViewService.create(owner=self.actor, name="Second", filters={"priority": "normal"}, ordering="due_at", is_default=True)
        first.refresh_from_db()
        self.assertFalse(first.is_default)
        self.assertTrue(second.is_default)
        with self.assertRaises(TaskValidationError): SavedViewService.create(owner=self.actor, name="Bad", filters={"raw_sql": "DROP"})
        with self.assertRaises(TaskValidationError): SavedViewValidator.validate_ordering("password")
        stranger = Employee.objects.create(first_name="Stranger")
        with self.assertRaises(TaskBusinessError): SavedViewService.update(view=second, owner=stranger, name="Stolen")

    def test_system_views(self):
        queryset = Task.objects.all()
        self.assertIn(self.mine, SystemViewService.apply(queryset, self.actor, "MY_TASKS"))
        self.assertIn(self.mine, SystemViewService.apply(queryset, self.actor, "CREATED_BY_ME"))
        self.assertIn(self.watched, SystemViewService.apply(queryset, self.actor, "WATCHING"))
        self.assertIn(self.mine, SystemViewService.apply(queryset, self.actor, "WITHOUT_DEADLINE"))

    def test_available_actions_and_counters_for_superuser(self):
        actions = TaskUXService.available_actions(self.mine, self.actor, is_superuser=True)
        self.assertIn("publish", actions)
        self.assertIn("comment", actions)
        role = Role.objects.create(code="ux-global", name="UX Global")
        permission = Permission.objects.create(code="task.view", name="View")
        RolePermission.objects.create(role=role, permission=permission, scope=Scope.GLOBAL)
        EmployeeRole.objects.create(employee=self.actor, role=role)
        counters = TaskUXService.counters(self.actor)
        self.assertEqual(counters["my_tasks"], 1)
        self.assertEqual(counters["created_by_me"], 1)
        self.assertEqual(counters["watching"], 1)


class CompletionApiTests(CompletionPhaseTestCase):
    def setUp(self):
        super().setUp()
        self.client = APIClient(); self.client.force_authenticate(self.user)

    def test_templates_recurrence_saved_views_and_ux_endpoints(self):
        response = self.client.post("/api/internal/v1/task-templates/", {
            "name": "API Template", "task_title": "API generated",
            "responsible_target": str(self.target.pk), "default_priority": "high",
            "deadline_rule": "after_creation", "deadline_offset": "01:00:00",
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        template_id = response.data["id"]
        task_response = self.client.post(f"/api/internal/v1/task-templates/{template_id}/create-task/", {"create_and_publish": True}, format="json")
        self.assertEqual(task_response.status_code, 201, task_response.data)
        self.assertEqual(task_response.data["status"], TaskStatus.OPEN)

        starts = timezone.now().replace(microsecond=0)
        response = self.client.post("/api/internal/v1/task-recurrences/", {
            "name": "API Recurrence", "task_template": template_id,
            "rrule": "FREQ=DAILY", "timezone": "Asia/Novosibirsk",
            "starts_at": starts.isoformat(),
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        recurrence_id = response.data["id"]
        self.assertEqual(self.client.post(f"/api/internal/v1/task-recurrences/{recurrence_id}/pause/", {}, format="json").status_code, 200)
        self.assertEqual(self.client.post(f"/api/internal/v1/task-recurrences/{recurrence_id}/resume/", {}, format="json").status_code, 200)

        response = self.client.post("/api/internal/v1/task-saved-views/", {"name": "My Drafts", "filters": {"status": "draft"}, "ordering": "-created_at", "is_default": True}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        saved_id = response.data["id"]
        self.assertEqual(self.client.get(f"/api/internal/v1/tasks/?saved_view={saved_id}").status_code, 200)
        self.assertEqual(self.client.get("/api/internal/v1/tasks/?system_view=WITHOUT_DEADLINE").status_code, 200)
        self.assertEqual(self.client.get("/api/internal/v1/tasks/counters/").status_code, 200)
