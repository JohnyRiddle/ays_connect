from datetime import timedelta
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from accounts.models import User
from employees.models import Employee, Position, AssignmentTarget
from access_control.models import Role, Permission, RolePermission, EmployeeRole
from organizations.models import OrgUnit, Location
from audit.models import AuditEvent
from events.models import OutboxEvent
from notifications.models import Notification
from notifications.services import ingest_event
from .models import Task, TaskDeadlineHistory
from .services import TaskService
from .collaboration import CollaborationService
from .policies import TaskAccessPolicy
from .exceptions import TaskBusinessError


def grant(employee, codes, scope='participating'):
    role = Role.objects.create(code='test-' + str(employee.pk) + '-' + scope, name='Synthetic patch role')
    for code in codes:
        permission, _ = Permission.objects.get_or_create(code=code, defaults={'name': code})
        RolePermission.objects.create(role=role, permission=permission, scope=scope)
    EmployeeRole.objects.create(employee=employee, role=role)
    return role


class TaskPatchTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(username='patch-admin', email='admin@patch.invalid')
        self.author = Employee.objects.create(user=self.admin, first_name='Synthetic author')
        self.unit = OrgUnit.objects.create(name='Synthetic IT')
        position = Position.objects.create(name='Synthetic head', org_unit=self.unit)
        self.unit.manager_position = position; self.unit.save()
        self.head_user = User.objects.create_user(username='patch-head', email='head@patch.invalid')
        self.head = Employee.objects.create(user=self.head_user, first_name='Synthetic head', org_unit=self.unit, position_ref=position)
        self.member_user = User.objects.create_user(username='patch-member', email='member@patch.invalid')
        self.member = Employee.objects.create(user=self.member_user, first_name='Synthetic member', org_unit=self.unit)
        self.other_user = User.objects.create_user(username='patch-other', email='other@patch.invalid')
        self.other = Employee.objects.create(user=self.other_user, first_name='Synthetic outsider')
        grant(self.head, ['task.view', 'task.assign', 'task.reassign', 'task.comment'])
        grant(self.head, ['employee.view', 'org_unit.view'], 'global')
        grant(self.member, ['task.view', 'task.comment', 'task.complete', 'task.reassign', 'task.change_deadline'])
        grant(self.other, ['task.view', 'task.comment'])

    def create(self, **data):
        return TaskService.create(actor=self.author, actor_user=self.admin, title='Synthetic patch task', responsible_department=self.unit, **data)

    def target(self, employee):
        return AssignmentTarget.objects.create(target_type='employee', employee=employee)

    def test_all_priority_deadlines_start_at_creation_and_blocking_is_explicit(self):
        for priority, hours in [('critical', 3), ('high', 24), ('normal', 72), ('low', 168)]:
            task = self.create(priority=priority)
            self.assertEqual(task.due_at, task.created_at + timedelta(hours=hours))
        with self.assertRaises(TaskBusinessError): self.create(priority='blocking')
        due = timezone.now() + timedelta(hours=1)
        self.assertEqual(self.create(priority='blocking', due_at=due).due_at, due)

    def test_priority_recalculation_uses_original_creation_and_audits(self):
        task = self.create()
        created = timezone.now() - timedelta(days=2)
        Task.objects.filter(pk=task.pk).update(created_at=created)
        task = TaskService.update(task=task, actor=self.author, actor_user=self.admin, version=1, priority='critical')
        self.assertEqual(task.due_at, created + timedelta(hours=3))
        self.assertTrue(task.is_overdue)
        self.assertEqual(TaskDeadlineHistory.objects.filter(task=task).count(), 1)
        self.assertTrue(AuditEvent.objects.filter(entity_id=str(task.pk), action='task.updated').exists())

    def test_head_is_automatic_executor_optional_and_head_stays_responsible(self):
        task = self.create()
        self.assertEqual(task.responsible_employee, self.head)
        self.assertIsNone(task.executor_employee)
        task = TaskService.reassign(task=task, actor=self.head, actor_user=self.head_user, version=1, assignment_type='executor', new_target=self.target(self.member))
        self.assertEqual(task.responsible_employee, self.head)
        self.assertEqual(task.executor_employee, self.member)

    def test_historical_tasks_need_department_before_every_transfer_to_work(self):
        for status, command in [('open', 'start'), ('waiting', 'resume'), ('review', 'reject'), ('completed', 'reopen')]:
            task = self.create(acceptance_policy='author')
            Task.objects.filter(pk=task.pk).update(status=status, responsible_department=None, completed_at=timezone.now() if status == 'completed' else None)
            task.refresh_from_db()
            with self.assertRaises(TaskBusinessError) as caught:
                getattr(TaskService, command)(task=task, actor=self.author, actor_user=self.admin, version=1, **({'reason': 'Synthetic readiness'} if command in {'reject', 'reopen'} else {}))
            self.assertEqual(caught.exception.code, 'task_department_required')
            task.refresh_from_db(); self.assertEqual(task.status, status)

    def test_department_head_missing_or_wrong_department_is_rejected(self):
        self.unit.manager_position = None; self.unit.save()
        with self.assertRaises(TaskBusinessError): self.create()

    def test_inactive_department_is_neither_assignable_nor_listed(self):
        self.unit.is_active = False; self.unit.save()
        with self.assertRaises(TaskBusinessError): self.create()
        client = APIClient(); client.force_authenticate(self.admin)
        self.assertNotIn(str(self.unit.pk), {d['id'] for d in client.get('/api/internal/v1/tasks/assignment-options/').data['departments']})

    def test_executor_outside_department_or_inactive_is_rejected(self):
        with self.assertRaises(TaskBusinessError): self.create(executor_target=self.target(self.other))
        self.member.is_active = False; self.member.save()
        with self.assertRaises(TaskBusinessError): self.create(executor_target=self.target(self.member))

    def test_employment_and_primary_location_do_not_grant_object_access(self):
        location = Location.objects.create(name='Synthetic restricted object')
        self.head.primary_location = location; self.head.save()
        with self.assertRaises(TaskBusinessError): self.create(location=location)

    def test_watchers_can_read_comment_but_cannot_manage_by_participation(self):
        task = self.create()
        CollaborationService.add_watcher(task=task, employee=self.member, actor=self.author, actor_user=self.admin)
        self.assertTrue(TaskAccessPolicy.allows(employee=self.member, permission='task.view', task=task))
        self.assertTrue(TaskAccessPolicy.allows(employee=self.member, permission='task.comment', task=task))
        for permission in ['task.complete', 'task.reassign', 'task.change_deadline']:
            self.assertFalse(TaskAccessPolicy.allows(employee=self.member, permission=permission, task=task))
        CollaborationService.remove_watcher(task=task, employee=self.member, actor=self.author, actor_user=self.admin)
        self.assertFalse(TaskAccessPolicy.allows(employee=self.member, permission='task.view', task=task))
        self.assertEqual(task.watcher_records.count(), 1)

    def test_watchers_without_object_access_are_rejected(self):
        task = self.create()
        task.location = Location.objects.create(name='Synthetic private object'); task.save()
        with self.assertRaises(TaskBusinessError):
            CollaborationService.add_watcher(task=task, employee=self.member, actor=self.author, actor_user=self.admin)

    def test_suspended_employee_cannot_be_mentioned_even_with_active_flag(self):
        task = self.create()
        self.member.status = 'suspended'; self.member.save()
        with self.assertRaises(TaskBusinessError):
            CollaborationService.add_comment(task=task, actor=self.author, actor_user=self.admin, body='Synthetic suspended mention', mentions=[self.member])

    @override_settings(NOTIFICATIONS_TELEGRAM_ENABLED=True)
    def test_mentions_do_not_grant_access_and_message_roles_are_deduplicated(self):
        task = self.create(executor_target=self.target(self.head))
        CollaborationService.add_watcher(task=task, employee=self.head, actor=self.author, actor_user=self.admin)
        comment = CollaborationService.add_comment(task=task, actor=self.author, actor_user=self.admin, body='Private synthetic message', mentions=[self.head, self.other])
        events = OutboxEvent.objects.filter(payload__comment_id=str(comment.pk)).order_by('created_at')
        for event in events: ingest_event(event)
        self.assertEqual(Notification.objects.filter(entity_id=str(task.pk), recipient_employee=self.head).count(), 1)
        self.assertFalse(Notification.objects.filter(recipient_employee=self.other).exists())
        self.assertFalse(TaskAccessPolicy.allows(employee=self.other, permission='task.view', task=task))

    def test_manual_deadline_requires_reason_even_in_draft(self):
        task = self.create()
        with self.assertRaises(TaskBusinessError): TaskService.change_deadline(task=task, actor=self.author, actor_user=self.admin, version=1, new_due_at=task.due_at)

    def test_department_change_needs_explicit_administrative_permission(self):
        task = self.create()
        role = grant(self.head, ['task.edit', 'task.reassign'], 'own')
        client = APIClient(); client.force_authenticate(self.head_user)
        self.assertFalse(client.get(f'/api/internal/v1/tasks/{task.pk}/').data['can_change_department'])
        with self.assertRaises(TaskBusinessError):
            TaskService.update(task=task, actor=self.head, actor_user=self.head_user, version=1, responsible_department=self.unit)
        permission, _ = Permission.objects.get_or_create(code='task.admin', defaults={'name': 'Explicit administration'})
        RolePermission.objects.create(role=role, permission=permission, scope='own')
        self.assertTrue(client.get(f'/api/internal/v1/tasks/{task.pk}/').data['can_change_department'])
        changed = TaskService.update(task=task, actor=self.head, actor_user=self.head_user, version=1, responsible_department=self.unit)
        self.assertEqual(changed.responsible_employee_id, self.head.pk)

    def test_assignment_options_show_new_active_members_and_exclude_outsiders(self):
        client = APIClient(); client.force_authenticate(self.admin)
        response = client.get('/api/internal/v1/tasks/assignment-options/', {'department': str(self.unit.pk)})
        self.assertEqual(response.status_code, 200, response.data)
        ids = {e['employee_id'] for e in response.data['executors']}
        self.assertIn(str(self.member.pk), ids); self.assertNotIn(str(self.other.pk), ids)
        self.member.is_active = False; self.member.save()
        response = client.get('/api/internal/v1/tasks/assignment-options/', {'department': str(self.unit.pk)})
        self.assertNotIn(str(self.member.pk), {e['employee_id'] for e in response.data['executors']})

    def test_request_creation_is_denied_even_to_admin_and_new_task_needs_department(self):
        client = APIClient(); client.force_authenticate(self.admin)
        self.assertEqual(client.post('/api/internal/v1/requests/', {}, format='json').status_code, 403)
        self.assertEqual(client.post('/api/internal/v1/tasks/', {'title': 'Synthetic'}, format='json').status_code, 400)

    def test_overdue_job_is_idempotent_and_preserves_location_events(self):
        from .overdue import process_overdue
        task = self.create(priority='blocking', due_at=timezone.now()-timedelta(hours=1))
        task = TaskService.publish(task=task, actor=self.author, actor_user=self.admin, version=1)
        location_event = OutboxEvent.objects.create(event_type='location.created', entity_type='Location', entity_id='synthetic', occurred_at=timezone.now(), payload={})
        self.assertEqual(process_overdue(), 1); self.assertEqual(process_overdue(), 0)
        location_event.refresh_from_db(); self.assertEqual(location_event.status, 'pending')


class ProjectDeadlinePatchTests(TestCase):
    setUp = TaskPatchTests.setUp

    def test_new_project_tasks_use_project_object_and_require_head_object_access(self):
        from projects.services import ProjectService, ProjectTaskService
        from organizations.models import LegalEntity
        from organizations.object_services import ObjectService
        entity = LegalEntity.objects.create(name='Synthetic project entity')
        location, _ = ObjectService.create(user=self.admin, key='synthetic-project-object', data={'name': 'Synthetic project object', 'business_type': 'office', 'timezone': 'Asia/Novosibirsk', 'legal_entity': entity})
        project = ProjectService.create(actor=self.author, actor_user=self.admin, name='Synthetic object-bound project', location=location, planned_end_at=timezone.now()+timedelta(days=8))
        with self.assertRaises(TaskBusinessError):
            ProjectTaskService.create_task(project=project, actor=self.author, actor_user=self.admin, project_version=1, task_data={'title': 'Synthetic forbidden object task', 'responsible_department': self.unit})
        role = grant(self.head, ['location.view'], 'location')
        EmployeeRole.objects.filter(employee=self.head, role=role).update(location=location)
        task = ProjectTaskService.create_task(project=project, actor=self.author, actor_user=self.admin, project_version=1, task_data={'title': 'Synthetic permitted object task', 'responsible_department': self.unit})
        self.assertEqual(task.location_id, location.pk)

    def test_old_link_without_task_deadline_uses_project_deadline_in_lists_and_overdue_job(self):
        from projects.services import ProjectService, ProjectTaskService
        from .selectors import TaskSelector
        from .serializers import TaskSerializer
        from .ux import SystemViewService, TaskUXService
        from .overdue import process_overdue
        project = ProjectService.create(actor=self.author, actor_user=self.admin, name='Synthetic historical project', planned_end_at=timezone.now()-timedelta(hours=1))
        task = TaskService.create(actor=self.author, actor_user=self.admin, title='Synthetic historical linked task', responsible_department=self.unit, source_type='project')
        ProjectTaskService.link(project=project, task=task, actor=self.author, actor_user=self.admin, project_version=1, task_version=1)
        Task.objects.filter(pk=task.pk).update(due_at=None, deadline_from_project=False, status='open')
        task.refresh_from_db()
        self.assertEqual(task.effective_due_at, project.planned_end_at)
        self.assertTrue(task.is_overdue)
        self.assertIsNotNone(TaskSerializer(task).data['due_at'])
        self.assertTrue(TaskSelector.apply_filters(Task.objects.all(), {'overdue': 'true'}).filter(pk=task.pk).exists())
        self.assertFalse(SystemViewService.apply(Task.objects.all(), self.author, 'without_deadline').filter(pk=task.pk).exists())
        self.assertEqual(TaskUXService.counters(self.author, Task.objects.all())['overdue'], 1)
        self.assertEqual(process_overdue(), 1); self.assertEqual(process_overdue(), 0)

    def test_project_deadline_inheritance_conflict_and_priority_is_inactive(self):
        from projects.services import ProjectService, ProjectTaskService, ProjectBusinessError
        from .serializers import TaskSerializer
        project = ProjectService.create(actor=self.author, actor_user=self.admin, name='Synthetic deadline project', planned_end_at=timezone.now()+timedelta(days=8))
        task = TaskService.create(actor=self.author, actor_user=self.admin, title='Synthetic project task', responsible_department=self.unit, source_type='project')
        ProjectTaskService.link(project=project, task=task, actor=self.author, actor_user=self.admin, project_version=project.version, task_version=task.version)
        task.refresh_from_db(); project.refresh_from_db()
        self.assertTrue(task.deadline_from_project); self.assertEqual(task.due_at, project.planned_end_at)
        self.assertIsNone(TaskSerializer(task).data['active_priority'])
        with self.assertRaises(TaskBusinessError): TaskService.update(task=task, actor=self.author, actor_user=self.admin, version=task.version, priority='critical')
        task = TaskService.change_deadline(task=task, actor=self.author, actor_user=self.admin, version=task.version, new_due_at=timezone.now()+timedelta(days=7), reason='Synthetic individual deadline')
        with self.assertRaises(ProjectBusinessError): ProjectService.edit(project=project, actor=self.author, actor_user=self.admin, version=project.version, changes={'planned_end_at': timezone.now()+timedelta(days=6)})
