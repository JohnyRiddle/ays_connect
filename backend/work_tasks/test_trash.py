from django.test import TestCase
from rest_framework.test import APIClient
from audit.models import AuditEvent
from events.models import OutboxEvent
from . import test_task_patch as fixture
from .models import Task, TaskComment
from .services import TaskService
from .exceptions import TaskValidationError
from .test_location_edit import grant


class TaskTrashTests(TestCase):
    def setUp(self):
        fixture.TaskPatchTests.setUp(self)
        self.task = fixture.TaskPatchTests.create(self)
        self.task = TaskService.cancel(task=self.task, actor=self.author, actor_user=self.admin, version=self.task.version, reason='Synthetic cancellation')
        self.comment = TaskComment.objects.create(task=self.task, author=self.author, body='Keep discussion')
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.url = f'/api/internal/v1/tasks/{self.task.pk}/'

    def command(self, action, version=None):
        return self.client.post(self.url+action+'/', {'version': self.task.version if version is None else version}, format='json')

    def test_trash_restore_preserves_history_status_and_content(self):
        self.assertEqual(self.command('trash').status_code, 200)
        self.task.refresh_from_db()
        self.assertIsNotNone(self.task.deleted_at)
        self.assertEqual(self.task.status, 'cancelled')
        self.assertEqual(self.client.get('/api/internal/v1/tasks/').data['count'], 0)
        self.assertEqual(self.client.get('/api/internal/v1/tasks/?deleted=true').data['count'], 1)
        self.assertEqual(self.client.get(self.url).data['available_actions'], ['restore'])
        self.assertEqual(self.client.get('/api/internal/v1/tasks/counters/').data['created_by_me'], 0)
        self.assertEqual(self.command('restore').status_code, 200)
        self.task.refresh_from_db()
        self.assertIsNone(self.task.deleted_at)
        self.assertEqual(self.task.status, 'cancelled')
        self.assertEqual(TaskComment.objects.get(pk=self.comment.pk).body, 'Keep discussion')
        self.assertEqual(self.client.get('/api/internal/v1/tasks/').data['count'], 1)
        self.assertEqual(AuditEvent.objects.filter(entity_id=str(self.task.pk), action__in=['task.trashed','task.restored']).count(), 2)
        self.assertEqual(OutboxEvent.objects.filter(entity_id=str(self.task.pk), event_type__in=['task.trashed','task.restored']).count(), 2)

    def test_rejects_stale_requests(self):
        self.assertGreaterEqual(self.command('trash', 999).status_code, 400)
        self.task.refresh_from_db(); self.assertIsNone(self.task.deleted_at)

    def test_all_statuses_can_be_trashed_and_restored_without_changing_work(self):
        from django.utils import timezone
        from datetime import timedelta
        for status in ['draft','open','in_progress','waiting','review','completed','cancelled']:
            with self.subTest(status=status):
                self.task.status=status
                self.task.completed_at=timezone.now() if status=='completed' else None
                self.task.due_at=timezone.now()-timedelta(hours=1)
                self.task.save(update_fields=['status','completed_at','due_at'])
                before=Task.objects.filter(pk=self.task.pk).values().get()
                self.assertEqual(self.command('trash').status_code,200)
                self.task.refresh_from_db();self.assertFalse(self.task.is_overdue)
                self.assertEqual(self.client.get(self.url).data['available_actions'],['restore'])
                self.assertEqual(self.command('restore').status_code,200)
                self.task.refresh_from_db()
                after=Task.objects.filter(pk=self.task.pk).values().get()
                self.assertLessEqual({k for k in before if before[k]!=after[k]}, {'version','updated_at','updated_by_id'})

    def test_deleted_active_task_skips_overdue_and_new_notifications(self):
        from datetime import timedelta
        from django.utils import timezone
        from .overdue import process_overdue
        from notifications.task_events import ingest_task_event
        from notifications.models import Notification
        self.task.status='open';self.task.due_at=timezone.now()-timedelta(hours=1)
        self.task.save(update_fields=['status','due_at'])
        event=OutboxEvent.objects.filter(entity_id=str(self.task.pk),event_type='task.created').get()
        self.assertEqual(self.command('trash').status_code,200)
        self.assertEqual(process_overdue(),0)
        before=Notification.objects.count();ingest_task_event(event)
        self.assertEqual(Notification.objects.count(),before)
        self.task.refresh_from_db()
        self.assertEqual(self.command('restore').status_code,200)
        self.assertEqual(process_overdue(),1)

    def test_service_mutation_of_deleted_task_is_blocked(self):
        from .collaboration import CollaborationService
        from .approvals import ApprovalService
        from uuid import uuid4
        stale=self.task
        self.assertEqual(self.command('trash').status_code,200)
        with self.assertRaises(TaskValidationError):
            CollaborationService.add_comment(task=stale,actor=self.author,actor_user=self.admin,body='No write')
        with self.assertRaises(TaskValidationError):
            ApprovalService.request_from_task(task=stale,actor=self.author,user=self.admin,approver=self.member,text='No write',command_id=uuid4())

    def test_active_restore_revalidates_members_and_stale_version(self):
        self.task.status='open';self.task.save(update_fields=['status'])
        self.assertEqual(self.command('trash').status_code,200)
        self.task.refresh_from_db()
        self.assertGreaterEqual(self.command('restore',self.task.version-1).status_code,400)
        self.head.is_active=False;self.head.save(update_fields=['is_active'])
        self.assertGreaterEqual(self.command('restore').status_code,400)
        self.task.refresh_from_db();self.assertIsNotNone(self.task.deleted_at)
        self.assertEqual(self.task.status,'open')

    def test_deleted_active_task_excluded_from_current_performance_counts(self):
        from datetime import timedelta
        from django.utils import timezone
        from performance.engine import aggregate_employee
        self.task.status='open';self.task.due_at=timezone.now()-timedelta(hours=1)
        self.task.save(update_fields=['status','due_at'])
        self.assertEqual(self.command('trash').status_code,200)
        now=timezone.now()
        rows=aggregate_employee(self.head,now-timedelta(days=1),now,'UTC')
        counts={row.metric_code:row.value for row in rows}
        self.assertEqual(counts['active_tasks'],0);self.assertEqual(counts['overdue_tasks'],0)

    def test_viewer_and_hidden_task_denied(self):
        grant(self.member, ['task.view'], 'global')
        self.client.force_authenticate(self.member_user)
        self.assertGreaterEqual(self.command('trash').status_code, 400)
        self.client.force_authenticate(self.other_user)
        self.assertEqual(self.command('trash').status_code, 404)
        self.task.refresh_from_db(); self.assertIsNone(self.task.deleted_at)

    def test_scoped_cancel_does_not_grant_restore_or_unrelated_access(self):
        self.task.executor_employee=self.member; self.task.save(update_fields=['executor_employee'])
        grant(self.member, ['task.cancel'], 'participating')
        self.client.force_authenticate(self.member_user)
        self.assertEqual(self.command('trash').status_code, 200)
        self.task.refresh_from_db()
        self.assertGreaterEqual(self.command('restore').status_code, 400)
        grant(self.member, ['task.reopen'], 'participating')
        self.assertEqual(self.command('restore').status_code, 200)

    def test_deleted_task_cannot_be_changed_or_hard_deleted(self):
        self.assertEqual(self.command('trash').status_code, 200)
        self.task.refresh_from_db()
        self.assertGreaterEqual(self.command('reopen').status_code, 400)
        self.assertGreaterEqual(self.client.post(self.url+'comments/', {'body':'Forbidden'}, format='json').status_code, 400)
        self.assertEqual(self.client.delete(self.url).status_code, 405)
        self.assertTrue(Task.objects.filter(pk=self.task.pk).exists())
        with self.assertRaises(TaskValidationError):
            TaskService.reopen(task=self.task, actor=self.author, actor_user=self.admin, version=self.task.version, reason='Do not bypass trash')

    def test_parent_with_children_cannot_be_trashed(self):
        child=fixture.TaskPatchTests.create(self, parent=self.task)
        self.assertGreaterEqual(self.command('trash').status_code, 400)
        self.assertTrue(Task.objects.filter(pk=child.pk).exists())

    def test_project_version_required_and_deleted_task_blocks_new_links(self):
        from projects.models import Project, ProjectTaskLink
        from projects.services import ProjectTaskService, ProjectBusinessError
        project=Project.objects.create(number='PRJ-TRASH-TEST', name='Synthetic project', created_by=self.admin, updated_by=self.admin)
        link=ProjectTaskLink.objects.create(project=project, task=self.task, linked_by=self.admin)
        self.assertGreaterEqual(self.command('trash').status_code, 400)
        link.is_active=False; link.save(update_fields=['is_active'])
        self.assertEqual(self.command('trash').status_code, 200)
        self.task.refresh_from_db()
        with self.assertRaises(ProjectBusinessError):
            ProjectTaskService.authorize_task(self.author, self.admin, self.task)
        with self.assertRaises(TaskValidationError):
            fixture.TaskPatchTests.create(self, parent=self.task)
