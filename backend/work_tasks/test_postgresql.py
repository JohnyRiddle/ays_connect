from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.db import connection, connections
from django.test import TransactionTestCase
from django.utils import timezone

from accounts.models import User
from employees.models import AssignmentTarget, Employee
from organizations.models import LegalEntity, OrgUnit

from .automation import RecurrenceService, TaskTemplateService
from .collaboration import CollaborationService
from .exceptions import TaskVersionConflict
from .models import Task, TaskOccurrence, TaskWatcher
from .services import TaskService


class PostgreSQLTaskConcurrencyTests(TransactionTestCase):
    """Real transaction races that SQLite cannot validate correctly."""

    reset_sequences = True

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if connection.vendor != "postgresql":
            raise cls.skipTest("PostgreSQL-specific quality gate")

    def setUp(self):
        self.user = User.objects.create_superuser(
            username="tasks-pg-admin", email="tasks-pg@test.local", password="pass"
        )
        self.legal_entity = LegalEntity.objects.create(name="Tasks PostgreSQL LE")
        self.org_unit = OrgUnit.objects.create(
            name="Tasks PostgreSQL Unit", legal_entity=self.legal_entity
        )
        self.actor = Employee.objects.create(
            user=self.user,
            first_name="Автор",
            legal_entity=self.legal_entity,
            org_unit=self.org_unit,
        )
        self.executor = Employee.objects.create(
            first_name="Исполнитель",
            legal_entity=self.legal_entity,
            org_unit=self.org_unit,
        )
        self.target = AssignmentTarget.objects.create(
            target_type=AssignmentTarget.Type.EMPLOYEE, employee=self.executor
        )

    def tearDown(self):
        connections.close_all()
        super().tearDown()

    @staticmethod
    def _parallel(callables):
        with ThreadPoolExecutor(max_workers=len(callables)) as pool:
            futures = [pool.submit(callback) for callback in callables]
            return [future.result(timeout=15) for future in futures]

    def test_concurrent_task_numbers_are_unique_and_sequential(self):
        count = 20
        barrier = Barrier(count)

        def create(title):
            connections.close_all()
            barrier.wait(timeout=5)
            task = TaskService.create(
                actor=Employee.objects.get(pk=self.actor.pk),
                actor_user=User.objects.get(pk=self.user.pk),
                title=title,
                responsible_target=AssignmentTarget.objects.get(pk=self.target.pk),
                legal_entity=LegalEntity.objects.get(pk=self.legal_entity.pk),
                org_unit=OrgUnit.objects.get(pk=self.org_unit.pk),
            )
            connections.close_all()
            return task.number

        numbers = self._parallel([lambda index=index: create(f"Concurrent {index}") for index in range(count)])

        self.assertEqual(len(set(numbers)), count)
        self.assertEqual(sorted(numbers), [f"TASK-{value:06d}" for value in range(1,count+1)])

    def test_optimistic_locking_rejects_one_concurrent_writer(self):
        task = TaskService.create(
            actor=self.actor,
            actor_user=self.user,
            title="Original",
            responsible_target=self.target,
        )
        barrier = Barrier(2)

        def update(title):
            connections.close_all()
            stale = Task.objects.get(pk=task.pk)
            actor = Employee.objects.get(pk=self.actor.pk)
            user = User.objects.get(pk=self.user.pk)
            barrier.wait(timeout=5)
            try:
                TaskService.update(
                    task=stale, actor=actor, actor_user=user, version=1, title=title
                )
                result = "updated"
            except TaskVersionConflict:
                result = "conflict"
            connections.close_all()
            return result

        results = self._parallel([lambda: update("First"), lambda: update("Second")])

        self.assertCountEqual(results, ["updated", "conflict"])
        task.refresh_from_db()
        self.assertEqual(task.version, 2)

    def test_concurrent_occurrence_processing_creates_one_task(self):
        template = TaskTemplateService.create(
            actor=self.actor,
            actor_user=self.user,
            name="Recurring template",
            task_title="Recurring task",
            responsible_target=self.target,
        )
        starts_at = timezone.now().replace(microsecond=0)
        rule = RecurrenceService.create(
            actor=self.actor,
            actor_user=self.user,
            name="Daily",
            task_template=template,
            rrule="FREQ=DAILY",
            timezone_name="UTC",
            starts_at=starts_at,
        )
        occurrence = TaskOccurrence.objects.create(
            recurrence_rule=rule, occurrence_at=starts_at
        )
        barrier = Barrier(2)

        def process():
            connections.close_all()
            item = TaskOccurrence.objects.get(pk=occurrence.pk)
            barrier.wait(timeout=5)
            result = RecurrenceService.process_occurrence(item)
            task_id = result.task_id
            connections.close_all()
            return task_id

        task_ids = self._parallel([process, process])

        occurrence.refresh_from_db()
        self.assertEqual(len(set(task_ids)), 1)
        self.assertEqual(Task.objects.filter(recurrence_rule=rule).count(), 1)
        self.assertEqual(occurrence.attempts, 1)

    def test_concurrent_watcher_add_returns_one_active_watcher(self):
        task = TaskService.create(
            actor=self.actor,
            actor_user=self.user,
            title="Watched task",
            responsible_target=self.target,
        )
        barrier = Barrier(2)

        def add():
            connections.close_all()
            current_task = Task.objects.get(pk=task.pk)
            actor = Employee.objects.get(pk=self.actor.pk)
            employee = Employee.objects.get(pk=self.executor.pk)
            user = User.objects.get(pk=self.user.pk)
            barrier.wait(timeout=5)
            watcher = CollaborationService.add_watcher(
                task=current_task,
                employee=employee,
                actor=actor,
                actor_user=user,
            )
            watcher_id = watcher.pk
            connections.close_all()
            return watcher_id

        watcher_ids = self._parallel([add, add])

        self.assertEqual(len(set(watcher_ids)), 1)
        self.assertEqual(
            TaskWatcher.objects.filter(
                task=task, employee=self.executor, removed_at__isnull=True
            ).count(),
            1,
        )
