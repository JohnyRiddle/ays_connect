from datetime import timedelta
from unittest.mock import patch

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from access_control.models import EmployeeRole, Permission, Role, RolePermission, Scope
from accounts.models import User
from audit.models import AuditEvent
from employees.models import AssignmentTarget, Employee, Position
from events.models import OutboxEvent
from organizations.models import LegalEntity, OrgUnit
from .exceptions import TaskBusinessError, TaskInvalidTransition, TaskValidationError, TaskVersionConflict
from .models import AcceptancePolicy, CompletionPolicy, Task, TaskAssignmentHistory, TaskStatus, TaskWaitingPeriod, WaitingReason
from .services import TaskService
from .state_machine import TaskStateMachine


class TaskCoreTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username="admin", email="admin@tasks.test", password="pass")
        self.legal_entity = LegalEntity.objects.create(name="Task LE")
        self.org_unit = OrgUnit.objects.create(name="Task Unit", legal_entity=self.legal_entity)
        self.actor = Employee.objects.create(user=self.user, first_name="Иван", last_name="Автор", legal_entity=self.legal_entity, org_unit=self.org_unit)
        self.executor = Employee.objects.create(first_name="Пётр", last_name="Исполнитель", legal_entity=self.legal_entity, org_unit=self.org_unit)
        self.target = AssignmentTarget.objects.create(target_type=AssignmentTarget.Type.EMPLOYEE, employee=self.executor)

    def create_task(self, **kwargs):
        data = {"actor": self.actor, "actor_user": self.user, "title": "Production task", "responsible_target": self.target, "legal_entity": self.legal_entity, "org_unit": self.org_unit}
        data.update(kwargs)
        return TaskService.create(**data)

    def publish_start(self, task):
        task = TaskService.publish(task=task, actor=self.actor, actor_user=self.user, version=task.version)
        return TaskService.start(task=task, actor=self.actor, actor_user=self.user, version=task.version)


class TaskCreationAndAssignmentTests(TaskCoreTestCase):
    def test_draft_has_uuid_sequential_number_history_audit_and_outbox(self):
        first = self.create_task()
        second = self.create_task(title="Second")
        self.assertEqual(first.number, "TASK-000001")
        self.assertEqual(second.number, "TASK-000002")
        self.assertEqual(first.status, TaskStatus.DRAFT)
        self.assertEqual(first.version, 1)
        self.assertEqual(first.priority, "normal")
        self.assertEqual(first.status_history.count(), 1)
        self.assertTrue(AuditEvent.objects.filter(entity_id=str(first.pk), action="task.created").exists())
        self.assertTrue(OutboxEvent.objects.filter(entity_id=str(first.pk), event_type="task.created").exists())

    def test_publish_snapshots_assignment_and_initial_deadline(self):
        due = timezone.now() + timedelta(days=2)
        task = TaskService.publish(task=self.create_task(due_at=due), actor=self.actor, actor_user=self.user, version=1)
        self.assertEqual(task.status, TaskStatus.OPEN)
        self.assertEqual(task.responsible_employee, self.executor)
        self.assertEqual(task.initial_due_at, due)
        self.executor.is_active = False
        self.executor.save(update_fields=["is_active"])
        task.refresh_from_db()
        self.assertEqual(task.responsible_employee_id, self.executor.pk)

    def test_ambiguous_position_is_rejected(self):
        position = Position.objects.create(name="Shared")
        self.executor.position_ref = position
        self.executor.save(update_fields=["position_ref"])
        Employee.objects.create(first_name="Second", position_ref=position)
        target = AssignmentTarget.objects.create(target_type=AssignmentTarget.Type.POSITION, position=position)
        task = self.create_task(responsible_target=target)
        with self.assertRaises(TaskBusinessError) as caught:
            TaskService.publish(task=task, actor=self.actor, actor_user=self.user, version=1)
        self.assertEqual(caught.exception.code, "task_assignment_ambiguous")


class TaskLifecycleTests(TaskCoreTestCase):
    def test_state_machine_allows_only_declared_transitions(self):
        for source, targets in TaskStateMachine.ALLOWED.items():
            for target in TaskStatus.values:
                if target in targets:
                    TaskStateMachine.validate(source, target)
                else:
                    with self.assertRaises(TaskInvalidTransition):
                        TaskStateMachine.validate(source, target)

    def test_start_pause_resume_preserves_first_start_and_waiting_history(self):
        task = self.publish_start(self.create_task())
        started_at = task.started_at
        task = TaskService.pause(task=task, actor=self.actor, actor_user=self.user, version=task.version, reason=WaitingReason.EXTERNAL)
        self.assertEqual(task.status, TaskStatus.WAITING)
        self.assertEqual(TaskWaitingPeriod.objects.filter(task=task, ended_at__isnull=True).count(), 1)
        task = TaskService.resume(task=task, actor=self.actor, actor_user=self.user, version=task.version)
        self.assertEqual(task.started_at, started_at)
        self.assertFalse(TaskWaitingPeriod.objects.filter(task=task, ended_at__isnull=True).exists())

    def test_waiting_other_requires_comment(self):
        task = self.publish_start(self.create_task())
        with self.assertRaises(TaskValidationError):
            TaskService.pause(task=task, actor=self.actor, actor_user=self.user, version=task.version, reason=WaitingReason.OTHER)

    def test_complete_without_review_and_reopen(self):
        task = self.publish_start(self.create_task())
        task = TaskService.complete(task=task, actor=self.actor, actor_user=self.user, version=task.version, completion_comment="Готово")
        self.assertEqual(task.status, TaskStatus.COMPLETED)
        self.assertIsNotNone(task.completed_at)
        with self.assertRaises(TaskValidationError):
            TaskService.reopen(task=task, actor=self.actor, actor_user=self.user, version=task.version, reason="")
        task = TaskService.reopen(task=task, actor=self.actor, actor_user=self.user, version=task.version, reason="Нужна доработка")
        self.assertEqual(task.status, TaskStatus.IN_PROGRESS)
        self.assertIsNone(task.completed_at)
        self.assertGreaterEqual(task.status_history.filter(to_status=TaskStatus.COMPLETED).count(), 1)

    def test_review_accept_and_reject(self):
        task = self.publish_start(self.create_task(acceptance_policy=AcceptancePolicy.AUTHOR))
        task = TaskService.complete(task=task, actor=self.executor, actor_user=self.user, version=task.version)
        self.assertEqual(task.status, TaskStatus.REVIEW)
        task = TaskService.reject(task=task, actor=self.actor, actor_user=self.user, version=task.version, reason="Исправить")
        self.assertEqual(task.status, TaskStatus.IN_PROGRESS)
        task = TaskService.complete(task=task, actor=self.executor, actor_user=self.user, version=task.version)
        task = TaskService.accept(task=task, actor=self.actor, actor_user=self.user, version=task.version)
        self.assertEqual(task.status, TaskStatus.COMPLETED)

    def test_cancel_closes_waiting_period(self):
        task = self.publish_start(self.create_task())
        task = TaskService.pause(task=task, actor=self.actor, actor_user=self.user, version=task.version, reason=WaitingReason.MATERIAL)
        task = TaskService.cancel(task=task, actor=self.actor, actor_user=self.user, version=task.version, reason="Больше не требуется")
        self.assertEqual(task.status, TaskStatus.CANCELLED)
        self.assertIsNotNone(task.cancelled_at)
        self.assertFalse(task.waiting_periods.filter(ended_at__isnull=True).exists())


class TaskDeadlineHierarchyConcurrencyTests(TaskCoreTestCase):
    def test_deadline_history_and_immutable_initial_due(self):
        initial = timezone.now() + timedelta(days=1)
        task = self.publish_start(self.create_task(due_at=initial))
        later = initial + timedelta(days=1)
        with self.assertRaises(TaskValidationError):
            TaskService.change_deadline(task=task, actor=self.actor, actor_user=self.user, version=task.version, new_due_at=later)
        task = TaskService.change_deadline(task=task, actor=self.actor, actor_user=self.user, version=task.version, new_due_at=later, reason="Поставка задержалась")
        self.assertEqual(task.initial_due_at, initial)
        self.assertEqual(task.deadline_history.count(), 1)

    def test_stale_version_cannot_mutate(self):
        task = self.create_task()
        with self.assertRaises(TaskVersionConflict):
            TaskService.update(task=task, actor=self.actor, actor_user=self.user, version=99, title="Stale")
        task.refresh_from_db()
        self.assertEqual(task.title, "Production task")

    def test_parent_cycle_and_children_completion_policy(self):
        parent = self.publish_start(self.create_task(completion_policy=CompletionPolicy.ALL_CHILDREN_COMPLETED))
        child = self.create_task(title="Child", parent=parent)
        with self.assertRaises(TaskValidationError):
            TaskService.move_parent(task=parent, actor=self.actor, actor_user=self.user, version=parent.version, parent=child)
        with self.assertRaises(TaskValidationError) as caught:
            TaskService.complete(task=parent, actor=self.actor, actor_user=self.user, version=parent.version)
        self.assertEqual(caught.exception.code, "task_children_incomplete")

    def test_transaction_rolls_back_task_history_audit_and_outbox(self):
        counts = (Task.objects.count(), AuditEvent.objects.count(), OutboxEvent.objects.count())
        with patch("work_tasks.services.DomainEventService.publish", side_effect=RuntimeError("event failed")):
            with self.assertRaises(RuntimeError):
                self.create_task(title="Rollback")
        self.assertEqual((Task.objects.count(), AuditEvent.objects.count(), OutboxEvent.objects.count()), counts)


class TaskApiSecurityTests(TestCase):
    def setUp(self):
        self.le1, self.le2 = LegalEntity.objects.create(name="LE1"), LegalEntity.objects.create(name="LE2")
        self.u1, self.u2 = OrgUnit.objects.create(name="U1", legal_entity=self.le1), OrgUnit.objects.create(name="U2", legal_entity=self.le2)
        self.user = User.objects.create_user(username="employee", email="employee@task.test", password="pass")
        self.employee = Employee.objects.create(user=self.user, first_name="Viewer", legal_entity=self.le1, org_unit=self.u1)
        self.other = Employee.objects.create(first_name="Other", legal_entity=self.le2, org_unit=self.u2)
        self.target1 = AssignmentTarget.objects.create(target_type=AssignmentTarget.Type.EMPLOYEE, employee=self.employee)
        self.target2 = AssignmentTarget.objects.create(target_type=AssignmentTarget.Type.EMPLOYEE, employee=self.other)
        role = Role.objects.create(code="participant", name="Participant")
        for code in (
            "task.create", "task.view", "task.edit", "task.assign", "task.reassign",
            "task.change_deadline", "task.start", "task.pause", "task.complete",
            "task.accept", "task.reject", "task.cancel", "task.reopen",
        ):
            permission = Permission.objects.create(code=code, name=code)
            RolePermission.objects.create(role=role, permission=permission, scope=Scope.PARTICIPATING)
        EmployeeRole.objects.create(employee=self.employee, role=role)
        self.own = Task.objects.create(number="TASK-100001", title="Own", author=self.employee, responsible_target=self.target1, responsible_employee=self.employee, created_by=self.user, updated_by=self.user)
        other_user = User.objects.create_user(username="other", email="other@task.test")
        self.foreign = Task.objects.create(number="TASK-100002", title="Foreign", author=self.other, responsible_target=self.target2, responsible_employee=self.other, created_by=other_user, updated_by=other_user)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_list_and_detail_prevent_idor(self):
        response = self.client.get("/api/internal/v1/tasks/")
        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in response.data["results"]}
        self.assertIn(str(self.own.pk), ids)
        self.assertNotIn(str(self.foreign.pk), ids)
        self.assertEqual(self.client.get(f"/api/internal/v1/tasks/{self.foreign.pk}/").status_code, 404)

    def test_create_api_produces_draft(self):
        response = self.client.post("/api/internal/v1/tasks/", {"title": "API task", "responsible_target": str(self.target1.pk)}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["status"], TaskStatus.DRAFT)

    def test_api_lifecycle_patch_assignment_deadline_review_and_cancel(self):
        response = self.client.post("/api/internal/v1/tasks/", {
            "title": "Lifecycle", "responsible_target": str(self.target1.pk),
            "acceptance_policy": AcceptancePolicy.AUTHOR,
            "due_at": (timezone.now() + timedelta(days=1)).isoformat(),
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        task_id, version = response.data["id"], response.data["version"]

        response = self.client.patch(f"/api/internal/v1/tasks/{task_id}/", {"version": version, "title": "Updated"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        version = response.data["version"]

        for command, payload in (
            ("publish", {}), ("start", {}),
            ("pause", {"reason": WaitingReason.EXTERNAL}), ("resume", {}),
        ):
            response = self.client.post(f"/api/internal/v1/tasks/{task_id}/{command}/", {"version": version, **payload}, format="json")
            self.assertEqual(response.status_code, 200, (command, response.data))
            version = response.data["version"]

        response = self.client.post(f"/api/internal/v1/tasks/{task_id}/deadline/", {"version": version, "due_at": (timezone.now() + timedelta(days=2)).isoformat(), "reason": "Новый срок"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        version = response.data["version"]
        response = self.client.post(f"/api/internal/v1/tasks/{task_id}/reassign/", {"version": version, "assignment_type": "responsible", "target": str(self.target2.pk), "reason": "Передача"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        version = response.data["version"]

        response = self.client.post(f"/api/internal/v1/tasks/{task_id}/complete/", {"version": version, "completion_comment": "Готово"}, format="json")
        self.assertEqual(response.data["status"], TaskStatus.REVIEW)
        version = response.data["version"]
        response = self.client.post(f"/api/internal/v1/tasks/{task_id}/reject/", {"version": version, "reason": "Исправить"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        version = response.data["version"]
        response = self.client.post(f"/api/internal/v1/tasks/{task_id}/complete/", {"version": version}, format="json")
        version = response.data["version"]
        response = self.client.post(f"/api/internal/v1/tasks/{task_id}/accept/", {"version": version, "comment": "Принято"}, format="json")
        self.assertEqual(response.data["status"], TaskStatus.COMPLETED)
        version = response.data["version"]
        response = self.client.post(f"/api/internal/v1/tasks/{task_id}/reopen/", {"version": version, "reason": "Дополнение"}, format="json")
        version = response.data["version"]
        response = self.client.post(f"/api/internal/v1/tasks/{task_id}/cancel/", {"version": version, "reason": "Отмена"}, format="json")
        self.assertEqual(response.data["status"], TaskStatus.CANCELLED)

    def test_api_stale_version_returns_409_error_contract(self):
        response = self.client.patch(f"/api/internal/v1/tasks/{self.own.pk}/", {"version": 99, "title": "Stale"}, format="json")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["error"]["code"], "task_version_conflict")
