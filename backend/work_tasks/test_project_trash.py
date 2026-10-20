from datetime import timedelta
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient
from projects.models import Project, ProjectTaskLink, ProjectTaskLinkHistory, ProjectStage
from projects.services import ProjectService, ProjectTaskService, ProjectBusinessError
from . import test_task_patch as fixture
from .services import TaskService
from .models import Task
from .exceptions import TaskVersionConflict, TaskValidationError
from .test_location_edit import grant


class ProjectTrashTests(TestCase):
    def setUp(self):
        fixture.TaskPatchTests.setUp(self)
        self.task=fixture.TaskPatchTests.create(self)
        self.task.due_at=None;self.task.status='open';self.task.save(update_fields=['due_at','status'])
        self.project=ProjectService.create(actor=self.author,actor_user=self.admin,name='Synthetic trash project',manager=self.author,planned_end_at=timezone.now()+timedelta(days=10))
        self.stage=ProjectService.create_stage(project=self.project,actor=self.author,actor_user=self.admin,version=self.project.version,name='Synthetic stage')
        self.project.refresh_from_db()
        self.link=ProjectTaskService.link(project=self.project,task=self.task,actor=self.author,actor_user=self.admin,project_version=self.project.version,task_version=self.task.version,stage=self.stage)
        self.task.refresh_from_db();self.project.refresh_from_db()
        self.client=APIClient();self.client.force_authenticate(self.admin)
        self.url=f'/api/internal/v1/tasks/{self.task.pk}/'

    def command(self, name, **extra):
        return self.client.post(self.url+name+'/',{'version':self.task.version,'project_version':self.project.version,**extra},format='json')

    def refresh(self):
        self.task.refresh_from_db();self.project.refresh_from_db()

    def test_project_links_and_history_survive_and_deadline_uses_current_project(self):
        link_before=ProjectTaskLink.objects.values().get(pk=self.link.pk)
        history=list(ProjectTaskLinkHistory.objects.filter(task=self.task).values())
        self.assertEqual(self.command('trash').status_code,200);self.refresh()
        old_due=self.task.due_at
        base=f'/api/internal/v1/projects/{self.project.pk}/'
        self.assertEqual(self.client.get(base+'tasks/').data['count'],0)
        self.assertEqual(self.client.get(base+'counters/').data['available'],0)
        future=self.project.planned_end_at+timedelta(days=3)
        ProjectService.edit(project=self.project,actor=self.author,actor_user=self.admin,version=self.project.version,changes={'planned_end_at':future})
        self.refresh();self.assertEqual(self.task.due_at,old_due)
        self.assertEqual(self.command('restore').status_code,200);self.refresh()
        self.assertEqual(self.task.due_at,future);self.assertEqual(self.task.status,'open')
        self.assertEqual(ProjectTaskLink.objects.values().get(pk=self.link.pk),link_before)
        self.assertEqual(list(ProjectTaskLinkHistory.objects.filter(task=self.task).values()),history)
        self.assertEqual(self.client.get(base+'tasks/').data['count'],1)
        self.assertEqual(self.client.get(base+'counters/').data['available'],1)

    def test_stale_project_and_missing_project_permission_fail(self):
        self.assertEqual(self.command('trash',project_version=999).status_code,409)
        grant(self.head,['task.cancel','task.reopen'],'global')
        self.client.force_authenticate(self.head_user)
        self.assertGreaterEqual(self.command('trash').status_code,400)
        self.task.refresh_from_db();self.assertIsNone(self.task.deleted_at)

    def test_project_can_complete_without_deleted_tasks_but_restore_cannot_reopen_it(self):
        self.assertEqual(self.command('trash').status_code,200);self.refresh()
        self.project=ProjectService.transition(project=self.project,actor=self.author,actor_user=self.admin,version=self.project.version,action='start')
        self.project=ProjectService.transition(project=self.project,actor=self.author,actor_user=self.admin,version=self.project.version,action='complete')
        self.assertGreaterEqual(self.command('restore').status_code,400);self.refresh()
        self.assertEqual(self.project.status,'completed');self.assertIsNotNone(self.task.deleted_at)
        with self.assertRaises(ProjectBusinessError):
            ProjectService.delete_stage(project=self.project,stage=self.stage,actor=self.author,actor_user=self.admin,version=self.project.version)
        self.assertTrue(ProjectStage.objects.filter(pk=self.stage.pk).exists())

    def test_parent_links_survive_and_restore_requires_open_parent(self):
        parent=fixture.TaskPatchTests.create(self)
        self.task.parent=parent;self.task.save(update_fields=['parent'])
        with self.assertRaises(TaskValidationError):TaskService.trash(task=parent,actor=self.author,actor_user=self.admin,version=parent.version)
        self.assertEqual(self.command('trash').status_code,200);self.refresh()
        parent=TaskService.trash(task=parent,actor=self.author,actor_user=self.admin,version=parent.version)
        self.assertGreaterEqual(self.command('restore').status_code,400)
        TaskService.restore(task=parent,actor=self.author,actor_user=self.admin,version=parent.version)
        self.assertEqual(self.command('restore').status_code,200);self.refresh()
        self.assertEqual(self.task.parent_id,parent.pk)


class ProjectTrashConcurrencyTests(TransactionTestCase):
    def test_project_change_racing_trash_never_uses_stale_version(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        from django.db import transaction, close_old_connections
        from projects.services import project_lock
        ProjectTrashTests.setUp(self)
        started=Event()
        def attempt():
            close_old_connections();started.set()
            try:
                TaskService.trash(task=self.task,actor=self.author,actor_user=self.admin,version=self.task.version,project_version=self.project.version)
                return 'unexpected success'
            except TaskVersionConflict:return 'conflict'
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic():
                project_lock(self.project.pk)
                future=pool.submit(attempt);self.assertTrue(started.wait(5))
                Project.objects.filter(pk=self.project.pk).update(version=self.project.version+1)
            self.assertEqual(future.result(timeout=15),'conflict')
        self.task.refresh_from_db();self.assertIsNone(self.task.deleted_at)
