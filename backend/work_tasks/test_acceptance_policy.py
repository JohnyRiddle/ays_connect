from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.contrib import admin
from django.db import connections, close_old_connections
from django.test import TransactionTestCase, RequestFactory
from django.utils import timezone
from .tests import TaskCoreTestCase
from .models import Task
from .services import TaskService
from .exceptions import TaskValidationError, TaskVersionConflict


class AcceptancePolicyTests(TaskCoreTestCase):
    def test_responsible_reassignment_is_not_a_new_reviewer_api(self):
        from employees.models import Employee, AssignmentTarget
        replacement=Employee.objects.create(first_name='Replacement reviewer')
        target=AssignmentTarget.objects.create(target_type='employee',employee=replacement)
        for policy in ('author','responsible'):
            task=self.publish_start(self.create_task(acceptance_policy=policy))
            task=TaskService.reassign(task=task,actor=self.actor,actor_user=self.user,version=task.version,
                assignment_type='responsible',new_target=target,reason='Synthetic reassignment')
            task.refresh_from_db()
            self.assertEqual(task.acceptance_policy,policy)
            self.assertTrue(task.acceptance_policy_locked)
            expected=self.actor if policy=='author' else replacement
            TaskService._validate_reviewer(task,expected)
            with self.assertRaises(TaskValidationError):TaskService._validate_reviewer(task,self.executor)
            with self.assertRaises(TaskValidationError):self.change(task,acceptance_policy='none')

    def change(self,task,**changes):
        return TaskService.update(task=task,actor=self.actor,actor_user=self.user,version=task.version,**changes)

    def test_draft_change_and_published_superuser_denial(self):
        task=self.change(self.create_task(),acceptance_policy='author')
        task=self.publish_start(task)
        with self.assertRaises(TaskValidationError) as error:self.change(task,acceptance_policy='responsible',title='Forbidden')
        self.assertEqual(error.exception.code,'task_acceptance_policy_frozen')
        task.refresh_from_db();self.assertEqual(task.acceptance_policy,'author');self.assertEqual(task.title,'Production task')

    def test_same_policy_noop_after_cancel(self):
        task=self.publish_start(self.create_task(acceptance_policy='author'))
        task=TaskService.cancel(task=task,actor=self.actor,actor_user=self.user,version=task.version,reason='Synthetic')
        version=task.version;self.change(task,acceptance_policy='author')
        task.refresh_from_db();self.assertEqual(task.version,version)
        with self.assertRaises(TaskValidationError):self.change(task,acceptance_policy='none')

    def test_reopen_and_forced_draft_keep_policy_lock(self):
        task=self.publish_start(self.create_task(acceptance_policy='author'))
        Task.objects.filter(pk=task.pk).update(status='completed',completed_at=timezone.now())
        task.refresh_from_db()
        task=TaskService.reopen(task=task,actor=self.actor,actor_user=self.user,version=task.version,reason='Synthetic')
        with self.assertRaises(TaskValidationError):self.change(task,acceptance_policy='none')
        Task.objects.filter(pk=task.pk).update(status='draft',acceptance_policy_locked=False)
        task.refresh_from_db();self.assertTrue(task.acceptance_policy_locked)
        with self.assertRaises(TaskValidationError):self.change(task,acceptance_policy='none')

    def test_orm_save_update_bulk_atomic_and_noop(self):
        task=self.publish_start(self.create_task(acceptance_policy='author'))
        task.acceptance_policy='none';task.title='Forbidden'
        with self.assertRaises(TaskValidationError):task.save()
        with self.assertRaises(TaskValidationError):Task.objects.filter(pk=task.pk).update(acceptance_policy='none',title='Forbidden')
        with self.assertRaises(TaskValidationError):Task.objects.bulk_update([task],['acceptance_policy','title'])
        task.refresh_from_db();self.assertEqual(task.title,'Production task')
        Task.objects.filter(pk=task.pk).update(acceptance_policy='author')

    def test_admin_forged_post_rejected_before_other_fields(self):
        task=self.publish_start(self.create_task(acceptance_policy='author'))
        request=RequestFactory().post('/',{'acceptance_policy':'none','title':'Forbidden'})
        request.user=self.user
        response=admin.site._registry[Task].changeform_view(request,str(task.pk))
        self.assertEqual(response.status_code,400)
        task.refresh_from_db();self.assertEqual(task.title,'Production task')


class AcceptancePolicyConcurrencyTests(TransactionTestCase):
    setUp=TaskCoreTestCase.setUp
    create_task=TaskCoreTestCase.create_task
    def test_publish_races_draft_edit(self):
        task=self.create_task(acceptance_policy='author');barrier=Barrier(2)
        def operation(publish):
            close_old_connections()
            try:
                with connections['default'].cursor() as cursor:
                    cursor.execute("SET lock_timeout='5s'")
                    cursor.execute("SET statement_timeout='10s'")
                barrier.wait(timeout=10)
                try:
                    if publish:TaskService.publish(task=task,actor=self.actor,actor_user=self.user,version=1)
                    else:TaskService.update(task=task,actor=self.actor,actor_user=self.user,version=1,acceptance_policy='responsible')
                    return 'published' if publish else 'edited'
                except TaskVersionConflict:return 'conflict'
            finally:connections['default'].close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs=[pool.submit(operation,value) for value in [True,False]]
            results=[job.result(timeout=30) for job in jobs]
        self.assertEqual(results.count('conflict'),1)
        task.refresh_from_db()
        if task.status=='draft':TaskService.publish(task=task,actor=self.actor,actor_user=self.user,version=task.version)
        task.refresh_from_db();self.assertTrue(task.acceptance_policy_locked)
        self.assertEqual(task.acceptance_policy,'responsible' if 'edited' in results else 'author')
        with self.assertRaises(TaskValidationError):TaskService.update(task=task,actor=self.actor,actor_user=self.user,version=task.version,acceptance_policy='none')
