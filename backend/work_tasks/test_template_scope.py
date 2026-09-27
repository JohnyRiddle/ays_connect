from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from accounts.models import User
from access_control.models import Permission, Role, RolePermission, EmployeeRole
from employees.models import Employee
from organizations.models import OrgUnit
from .models import TaskTemplate, TaskRecurrenceRule
from .automation import TaskTemplateService, RecurrenceService
from .exceptions import TaskBusinessError


class TemplateScopeTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user(username='scope',email='scope@example.test')
        self.unit=OrgUnit.objects.create(name='Allowed')
        self.outside=OrgUnit.objects.create(name='Outside')
        self.actor=Employee.objects.create(user=self.user,org_unit=self.unit)
        role=Role.objects.create(code='scope-test',name='Synthetic')
        for code,scope in [('task_template.view','global'),('task_template.manage','org_unit'),
                           ('task_template.use','org_unit'),('task_recurrence.view','global'),
                           ('task_recurrence.manage','org_unit'),('task_recurrence.run','org_unit')]:
            permission,_=Permission.objects.get_or_create(code=code)
            RolePermission.objects.create(role=role,permission=permission,scope=scope)
        self.grant=EmployeeRole.objects.create(employee=self.actor,role=role,org_unit=self.unit)
        self.local=TaskTemplate.objects.create(name='Local',task_title='Local',created_by=self.actor,org_unit=self.unit)
        self.remote=TaskTemplate.objects.create(name='Remote',task_title='Remote',created_by=self.actor,org_unit=self.outside)
        self.client=APIClient();self.client.force_authenticate(self.user)

    def test_global_read_does_not_expand_template_write_or_use(self):
        path=f'/api/internal/v1/task-templates/{self.remote.pk}/'
        self.assertEqual(self.client.get(path).status_code,200)
        self.assertEqual(self.client.patch(path,{'name':'Forbidden'}).status_code,404)
        self.assertEqual(self.client.post(path+'create-task/',{}).status_code,404)
        with self.assertRaises(TaskBusinessError):
            TaskTemplateService.update(template=self.remote,actor=self.actor,actor_user=self.user,name='Forbidden')
        self.remote.refresh_from_db();self.assertEqual(self.remote.name,'Remote')

    def test_template_cannot_be_created_or_moved_outside_scope(self):
        with self.assertRaises(TaskBusinessError):
            TaskTemplateService.create(actor=self.actor,actor_user=self.user,name='Forbidden',task_title='X',org_unit=self.outside)
        with self.assertRaises(TaskBusinessError):
            TaskTemplateService.update(template=self.local,actor=self.actor,actor_user=self.user,org_unit=self.outside,name='Forbidden')
        self.local.refresh_from_db();self.assertEqual(self.local.name,'Local')
        result=TaskTemplateService.update(template=self.local,actor=self.actor,actor_user=self.user,name='Allowed edit')
        self.assertEqual(result.name,'Allowed edit')

    def test_recurrence_cannot_be_changed_or_retargeted_outside_scope(self):
        rule=TaskRecurrenceRule.objects.create(name='Rule',task_template=self.remote,created_by=self.actor,
            rrule='FREQ=DAILY',timezone='UTC',starts_at=timezone.now())
        path=f'/api/internal/v1/task-recurrences/{rule.pk}/'
        self.assertEqual(self.client.get(path).status_code,200)
        self.assertEqual(self.client.post(path+'pause/',{}).status_code,404)
        with self.assertRaises(TaskBusinessError):
            RecurrenceService.pause(rule=rule,actor=self.actor,actor_user=self.user)
        rule.task_template=self.local;rule.save(update_fields=['task_template'])
        with self.assertRaises(TaskBusinessError):
            RecurrenceService.update(rule=rule,actor=self.actor,actor_user=self.user,task_template=self.remote)
        rule.refresh_from_db();self.assertEqual(rule.task_template_id,self.local.pk)

    def test_null_scope_never_matches_unassigned_template(self):
        self.grant.org_unit=None;self.grant.save(update_fields=['org_unit'])
        self.actor.org_unit=None;self.actor.save(update_fields=['org_unit'])
        self.local.org_unit=None;self.local.save(update_fields=['org_unit'])
        with self.assertRaises(TaskBusinessError):
            TaskTemplateService.update(template=self.local,actor=self.actor,actor_user=self.user,name='Forbidden')
