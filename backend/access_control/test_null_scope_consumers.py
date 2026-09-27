from types import SimpleNamespace
from django.test import TestCase
from accounts.models import User
from employees.models import Employee
from organizations.models import OrgUnit,LegalEntity
from work_tasks.models import Task
from work_tasks.policies import TaskAccessPolicy
from service_requests.policies import ServiceRequestAccessPolicy
from performance.access import visible_employees
from .models import Role,Permission,RolePermission,EmployeeRole


class NullScopeConsumerTests(TestCase):
    def test_missing_context_does_not_mean_all_unassigned_objects(self):
        user=User.objects.create_user(username='null-scope',email='null-scope@example.test')
        actor=Employee.objects.create(user=user)
        outside=Employee.objects.create(first_name='Unrelated')
        role=Role.objects.create(code='null-scope',name='Synthetic scoped business role')
        for code in ('task.view','request.view','performance.view'):
            permission,_=Permission.objects.get_or_create(code=code)
            RolePermission.objects.create(role=role,permission=permission,scope='org_unit')
        grant=EmployeeRole.objects.create(employee=actor,role=role)
        task=Task.objects.create(number='TASK-NULL-SCOPE',title='Unrelated',author=outside,created_by=user,updated_by=user)
        request=SimpleNamespace(requester_id=outside.pk,responsible_employee_id=None,assigned_employee_id=None,
            created_by_id=None,watcher_records=SimpleNamespace(filter=lambda **kwargs:SimpleNamespace(exists=lambda:False)),
            org_unit_id=None,legal_entity_id=None)
        for scope in ('org_unit','legal_entity'):
            RolePermission.objects.filter(role=role).update(scope=scope)
            self.assertFalse(TaskAccessPolicy.allows(employee=actor,permission='task.view',task=task))
            self.assertFalse(Task.objects.filter(TaskAccessPolicy.visibility_query(employee=actor)).exists())
            self.assertFalse(ServiceRequestAccessPolicy.allows(employee=actor,permission='request.view',request=request))
            # Both domain query builders use these identical nullable context fields.
            self.assertFalse(Task.objects.filter(ServiceRequestAccessPolicy.visibility_query(employee=actor)).exists())
            self.assertFalse(visible_employees(user).filter(pk=outside.pk).exists())
        entity=LegalEntity.objects.create(name='Assigned context')
        grant.legal_entity=entity;grant.save(update_fields=['legal_entity'])
        outside.legal_entity=entity;outside.save(update_fields=['legal_entity'])
        task.legal_entity=entity;task.save(update_fields=['legal_entity'])
        request.legal_entity_id=entity.pk
        self.assertTrue(TaskAccessPolicy.allows(employee=actor,permission='task.view',task=task))
        self.assertTrue(ServiceRequestAccessPolicy.allows(employee=actor,permission='request.view',request=request))
        self.assertTrue(visible_employees(user).filter(pk=outside.pk).exists())
