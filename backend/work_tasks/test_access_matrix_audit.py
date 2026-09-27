"""Regression: published acceptance cannot be disabled."""
from django.test import TestCase
from accounts.models import User
from access_control.models import Permission, Role, RolePermission, EmployeeRole
from employees.models import Employee
from .models import Task
from .services import TaskService


class AccessMatrixAuditTests(TestCase):
    def test_task_edit_cannot_remove_published_acceptance(self):
        user=User.objects.create_user(username='audit-synthetic',email='audit-synthetic@example.test',password=None)
        actor=Employee.objects.create(user=user,first_name='Synthetic audit')
        role=Role.objects.create(code='audit-task-edit',name='Disposable diagnostic grant')
        permission,_=Permission.objects.get_or_create(code='task.edit')
        RolePermission.objects.create(role=role,permission=permission,scope='global')
        admin_permission,_=Permission.objects.get_or_create(code='task.admin')
        RolePermission.objects.create(role=role,permission=admin_permission,scope='global')
        EmployeeRole.objects.create(employee=actor,role=role)
        task=Task.objects.create(number='AUDIT-ACCEPTANCE',title='Synthetic',author=actor,
            created_by=user,updated_by=user,status='in_progress',acceptance_policy='author')
        from .exceptions import TaskValidationError
        with self.assertRaises(TaskValidationError) as raised:
            TaskService.update(task=task,actor=actor,actor_user=user,version=task.version,acceptance_policy='none',title='Must not persist')
        self.assertEqual(raised.exception.code,'task_acceptance_policy_frozen')
        task.refresh_from_db()
        self.assertEqual(task.acceptance_policy,'author')
        self.assertEqual(task.title,'Synthetic')
        self.assertFalse(user.is_staff or user.is_superuser)
