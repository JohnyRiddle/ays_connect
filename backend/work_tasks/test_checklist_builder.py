from unittest.mock import patch
from rest_framework.test import APIClient
from audit.models import AuditEvent
from accounts.models import User
from employees.models import Employee
from .test_collaboration import CollaborationTestCase
from .collaboration import ChecklistService
from .exceptions import TaskValidationError, TaskVersionConflict
from .models import TaskChecklistItem
from .services import TaskService
from django.test import TransactionTestCase
from django.db import connection, connections, close_old_connections
from concurrent.futures import ThreadPoolExecutor
from unittest import skipUnless
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone


class ChecklistBuilderTests(CollaborationTestCase):
    def template(self, **kw):
        return ChecklistService.create_template(actor=self.actor, actor_user=self.user, name='Открытие объекта', items=[{'text':'Температура','section':'Кухня','answer_type':'number','min_value':0,'max_value':10,'required':True}], **kw)

    def test_template_schema_version_is_copied_and_old_tasks_are_unchanged(self):
        template=self.template()
        first=ChecklistService.from_template(task=self.task,template=template,actor=self.actor,actor_user=self.user)
        template=ChecklistService.update_template(template=template,actor=self.actor,actor_user=self.user,version=1,items=[{'text':'Новый пункт','answer_type':'single','options':['Да','Нет'],'section':'Зал'}])
        second=ChecklistService.from_template(task=self.task,template=template,actor=self.actor,actor_user=self.user)
        self.assertEqual(first.source_template_version,1)
        self.assertEqual(first.items.get().section,'Кухня')
        self.assertEqual(first.items.get().max_value,10)
        self.assertEqual(second.source_template_version,2)
        self.assertEqual(second.items.get().options,['Да','Нет'])

    def test_failed_replacement_rolls_back_schema_version_and_audit(self):
        template=self.template();before=AuditEvent.objects.count()
        with patch('work_tasks.collaboration.DomainEventService.publish',side_effect=RuntimeError('outbox failed')):
            with self.assertRaises(RuntimeError):
                ChecklistService.update_template(template=template,actor=self.actor,actor_user=self.user,version=1,items=[{'text':'Новый'}])
        template.refresh_from_db();self.assertEqual(template.version,1);self.assertEqual(template.items.get().text,'Температура');self.assertEqual(AuditEvent.objects.count(),before)

    def test_duplicate_positions_and_invalid_options_are_rejected_without_partial_update(self):
        template=self.template()
        for items in [[{'text':'A','position':1},{'text':'B','position':1}],[{'text':'A','answer_type':'single','options':['A','A']}]]:
            with self.assertRaises(TaskValidationError):
                ChecklistService.update_template(template=template,actor=self.actor,actor_user=self.user,items=items)
        self.assertEqual(template.items.count(),1)

    def test_all_answer_types_accept_false_zero_and_multiple_choices(self):
        for kind,answer,extra in [('checkbox',True,{}),('boolean',False,{}),('text',' Проверено ',{}),('number',0,{'min_value':0,'max_value':2}),('single','A',{'options':['A','B']}),('multiple',['A','B'],{'options':['A','B']})]:
            checklist=ChecklistService.create_manual(task=self.task,actor=self.actor,actor_user=self.user,name=kind,items=[{'text':kind,'answer_type':kind,**extra}])
            item=ChecklistService.set_completed(item=checklist.items.get(),actor=self.actor,actor_user=self.user,completed=True,answer=answer,version=1)
            self.assertTrue(item.is_completed);self.assertEqual(item.answer,answer.strip() if isinstance(answer,str) else answer)
            self.assertEqual(item.version,2)

    def test_invalid_answer_cannot_bypass_required_completion(self):
        self.start_task();template=self.template();checklist=ChecklistService.from_template(task=self.task,template=template,actor=self.actor,actor_user=self.user)
        for answer in [None,True,'2',-1,11,float('inf')]:
            with self.assertRaises(TaskValidationError):ChecklistService.set_completed(item=checklist.items.get(),actor=self.actor,actor_user=self.user,completed=True,answer=answer)
        with self.assertRaises(TaskValidationError):TaskService.complete(task=self.task,actor=self.actor,actor_user=self.user,version=self.task.version)
        self.assertFalse(checklist.items.get().is_completed)

    def test_stale_template_and_answer_versions_are_conflicts(self):
        template=self.template();ChecklistService.update_template(template=template,actor=self.actor,actor_user=self.user,version=1,name='Обновлён')
        with self.assertRaises(TaskVersionConflict):ChecklistService.update_template(template=template,actor=self.actor,actor_user=self.user,version=1,name='Перезапись')
        checklist=ChecklistService.from_template(task=self.task,template=template,actor=self.actor,actor_user=self.user)
        item=checklist.items.get();ChecklistService.set_completed(item=item,actor=self.actor,actor_user=self.user,completed=True,answer=1,version=1)
        with self.assertRaises(TaskVersionConflict):ChecklistService.set_completed(item=item,actor=self.actor,actor_user=self.user,completed=True,answer=2,version=1)
        self.assertEqual(TaskChecklistItem.objects.get(pk=item.pk).answer,1)

    def test_archive_prevents_new_attachments_but_keeps_answers(self):
        template=self.template();checklist=ChecklistService.from_template(task=self.task,template=template,actor=self.actor,actor_user=self.user)
        ChecklistService.set_completed(item=checklist.items.get(),actor=self.actor,actor_user=self.user,completed=True,answer=3)
        template=ChecklistService.update_template(template=template,actor=self.actor,actor_user=self.user,is_active=False)
        with self.assertRaises(TaskValidationError):ChecklistService.from_template(task=self.task,template=template,actor=self.actor,actor_user=self.user)
        self.assertEqual(checklist.items.get().answer,3)

    def test_terminal_task_answers_are_immutable_and_removal_is_soft(self):
        self.start_task();checklist=ChecklistService.create_manual(task=self.task,actor=self.actor,actor_user=self.user,name='Проверка',items=[{'text':'Готово'}])
        item=ChecklistService.set_completed(item=checklist.items.get(),actor=self.actor,actor_user=self.user,completed=True)
        self.task=TaskService.complete(task=self.task,actor=self.actor,actor_user=self.user,version=self.task.version)
        with self.assertRaises(TaskValidationError):ChecklistService.set_completed(item=item,actor=self.actor,actor_user=self.user,completed=False)
        with self.assertRaises(TaskValidationError):ChecklistService.remove_checklist(checklist=checklist,actor=self.actor,actor_user=self.user)

    def test_removing_active_checklist_preserves_answer_rows(self):
        checklist=ChecklistService.create_manual(task=self.task,actor=self.actor,actor_user=self.user,name='Проверка',items=[{'text':'Готово','required':True}])
        item=ChecklistService.set_completed(item=checklist.items.get(),actor=self.actor,actor_user=self.user,completed=True)
        ChecklistService.remove_checklist(checklist=checklist,actor=self.actor,actor_user=self.user)
        checklist.refresh_from_db();self.assertIsNotNone(checklist.removed_at)
        self.assertTrue(TaskChecklistItem.objects.get(pk=item.pk).is_completed)

    def test_api_rejects_foreign_user_and_stale_template_and_bad_input(self):
        client=APIClient();client.force_authenticate(self.user)
        root='/api/internal/v1/checklist-templates/'
        self.assertTrue(client.get(root+'capabilities/').data['can_manage'])
        data={'name':'Шаблон','items':[{'text':'Пункт','position':1,'answer_type':'boolean'}]}
        response=client.post(root,data,format='json');self.assertEqual(response.status_code,201,response.data)
        target=root+response.data['id']+'/'
        self.assertEqual(client.patch(target,{'version':1,'name':'Новый'},format='json').status_code,200)
        self.assertEqual(client.patch(target,{'version':1,'name':'Старый'},format='json').status_code,409)
        outsider=User.objects.create_user(username='checklist-outsider',email='outsider@checklist.invalid');Employee.objects.create(user=outsider)
        client.force_authenticate(outsider)
        self.assertFalse(client.get(root+'capabilities/').data['can_manage'])
        self.assertEqual(client.post(root,data,format='json').status_code,400)

    def test_api_attach_answer_and_complete_task_with_required_numeric_zero(self):
        self.start_task();template=self.template()
        client=APIClient();client.force_authenticate(self.user)
        root=f'/api/internal/v1/tasks/{self.task.pk}/'
        attached=client.post(root+'checklists/from-template/',{'template':str(template.pk)},format='json')
        self.assertEqual(attached.status_code,201,attached.data)
        checklist=attached.data;item=checklist['items'][0]
        answer_url=root+f"checklists/{checklist['id']}/items/{item['id']}/complete/"
        self.assertNotIn('complete',client.get(root).data['available_actions'])
        self.assertEqual(client.post(answer_url,{'answer':0},format='json').status_code,400)
        self.assertEqual(client.post(answer_url,{'answer':'0','version':1},format='json').status_code,400)
        saved=client.post(answer_url,{'answer':0,'version':1,'comment':'Проверено'},format='json')
        self.assertEqual(saved.status_code,200,saved.data);self.assertEqual(saved.data['answer'],0)
        self.assertIn('complete',client.get(root).data['available_actions'])
        self.assertEqual(client.post(answer_url,{'answer':1,'version':1},format='json').status_code,409)
        completed=client.post(root+'complete/',{'version':self.task.version},format='json')
        self.assertEqual(completed.status_code,200,completed.data)


class ChecklistConcurrentTests(TransactionTestCase):
    setUp = CollaborationTestCase.setUp

    @skipUnless(connection.vendor=='postgresql','PostgreSQL row locks required')
    def test_two_concurrent_answers_with_same_version_have_one_winner(self):
        checklist=ChecklistService.create_manual(task=self.task,actor=self.actor,actor_user=self.user,name='Параллельно',items=[{'text':'Число','answer_type':'number'}])
        iid=checklist.items.get().pk;actor_id=self.actor.pk;user_id=self.user.pk
        def write(value):
            close_old_connections()
            try:
                item=TaskChecklistItem.objects.get(pk=iid)
                ChecklistService.set_completed(item=item,actor=Employee.objects.get(pk=actor_id),actor_user=User.objects.get(pk=user_id),completed=True,answer=value,version=1)
                return 'saved'
            except TaskVersionConflict:return 'conflict'
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(write,[1,2]))
        self.assertCountEqual(results,['saved','conflict'])
        self.assertEqual(TaskChecklistItem.objects.get(pk=iid).version,2)


class ChecklistMigrationTests(TransactionTestCase):
    def test_upgrade_preserves_legacy_completed_checkbox_and_template(self):
        executor=MigrationExecutor(connection)
        latest=executor.loader.graph.leaf_nodes()
        old_targets=[('work_tasks','0008_task_deadline_is_manual') if app=='work_tasks' else (app,name) for app,name in latest]
        executor.migrate(old_targets)
        try:
            apps=executor.loader.project_state(old_targets).apps
            user=apps.get_model('accounts','User').objects.create(username='upgrade-checklist',email='upgrade@checklist.invalid')
            employee=apps.get_model('employees','Employee').objects.create(user=user,first_name='Upgrade')
            template=apps.get_model('work_tasks','ChecklistTemplate').objects.create(name='Старый шаблон',created_by=employee)
            apps.get_model('work_tasks','ChecklistTemplateItem').objects.create(template=template,text='Старый пункт',position=1,required=True)
            task=apps.get_model('work_tasks','Task').objects.create(number='TASK-UPGRADE',title='Upgrade',author=employee,created_by=user,updated_by=user)
            checklist=apps.get_model('work_tasks','TaskChecklist').objects.create(task=task,name='Старый чек-лист',created_by=employee,source_template=template)
            item=apps.get_model('work_tasks','TaskChecklistItem').objects.create(checklist=checklist,text='Выполнено ранее',position=1,required=True,is_completed=True,completed_by=employee,completed_at=timezone.now())
            iid=item.pk;tid=template.pk
        finally:
            MigrationExecutor(connection).migrate(latest)
        upgraded=TaskChecklistItem.objects.get(pk=iid)
        self.assertTrue(upgraded.is_completed);self.assertEqual(upgraded.answer_type,'checkbox');self.assertIsNone(upgraded.answer)
        self.assertEqual(upgraded.completed_by_id,employee.pk)
        from .models import ChecklistTemplate
        self.assertEqual(ChecklistTemplate.objects.get(pk=tid).version,1)
