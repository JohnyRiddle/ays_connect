"""Upgrade proof on synthetic PostgreSQL data, never a production-copy claim."""
import uuid
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


class PatchUpgradeTests(TransactionTestCase):
    def test_additions_preserve_task_assignments_history_grants_and_location_pending(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        old = [(app, migration) for app, migration in latest if app not in {'work_tasks', 'notifications'}]
        old += [('work_tasks', '0004_lock_acceptance_policy'), ('notifications', '0005_telegramwebhookevent_and_more')]
        try:
            executor.migrate(old)
            apps = executor.loader.project_state(old).apps
            User = apps.get_model('accounts', 'User')
            Employee = apps.get_model('employees', 'Employee')
            Target = apps.get_model('employees', 'AssignmentTarget')
            Task = apps.get_model('work_tasks', 'Task')
            History = apps.get_model('work_tasks', 'TaskStatusHistory')
            Outbox = apps.get_model('events', 'OutboxEvent')
            Permission = apps.get_model('access_control', 'Permission')
            Role = apps.get_model('access_control', 'Role')
            RolePermission = apps.get_model('access_control', 'RolePermission')
            EmployeeRole = apps.get_model('access_control', 'EmployeeRole')
            user = User.objects.create(username='synthetic-upgrade', email='upgrade@patch.invalid')
            employee = Employee.objects.create(user=user, first_name='Synthetic preserved employee')
            target = Target.objects.create(target_type='employee', employee=employee)
            task = Task.objects.create(number='TASK-UPGRADE-PRESERVED', title='Synthetic preserved task', author=employee, responsible_target=target, responsible_employee=employee, priority='high', created_by=user, updated_by=user)
            history = History.objects.create(task=task, to_status='draft', actor=employee)
            role = Role.objects.create(code='synthetic-upgrade-role', name='Synthetic preserved grant')
            permission, _ = Permission.objects.get_or_create(code='task.view', defaults={'name': 'View tasks'})
            grant = RolePermission.objects.create(role=role, permission=permission, scope='participating')
            assignment = EmployeeRole.objects.create(employee=employee, role=role)
            event = Outbox.objects.create(event_type='location.created', entity_type='Location', entity_id=str(uuid.uuid4()), occurred_at=timezone.now(), payload={'synthetic': True})
            frozen = (task.pk, task.number, task.responsible_target_id, task.responsible_employee_id, task.priority, task.version, task.due_at, history.pk, grant.pk, assignment.pk, event.event_id)
            executor = MigrationExecutor(connection); executor.migrate(latest)
            from work_tasks.models import Task as CurrentTask, TaskStatusHistory, TaskOverdueNotice
            from access_control.models import RolePermission as CurrentGrant, EmployeeRole as CurrentAssignment
            from events.models import OutboxEvent
            current = CurrentTask.objects.get(pk=task.pk)
            self.assertEqual(frozen, (current.pk, current.number, current.responsible_target_id, current.responsible_employee_id, current.priority, current.version, current.due_at, TaskStatusHistory.objects.get(pk=history.pk).pk, CurrentGrant.objects.get(pk=grant.pk).pk, CurrentAssignment.objects.get(pk=assignment.pk).pk, OutboxEvent.objects.get(pk=event.pk).event_id))
            self.assertIsNone(current.responsible_department_id)
            self.assertFalse(TaskOverdueNotice.objects.exists())
            self.assertEqual(OutboxEvent.objects.get(pk=event.pk).status, 'pending')
            self.assertTrue(CurrentAssignment.objects.get(pk=assignment.pk).is_active)
        finally:
            MigrationExecutor(connection).migrate(latest)
