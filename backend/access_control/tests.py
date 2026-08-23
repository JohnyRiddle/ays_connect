from datetime import timedelta
from django.test import TestCase
from django.utils import timezone

from employees.models import Employee
from organizations.models import LegalEntity, OrgUnit
from .models import EmployeeRole, Permission, Role, RolePermission, Scope
from .services import PermissionService


class PermissionServiceTests(TestCase):
    def setUp(self):
        self.le1 = LegalEntity.objects.create(name="LE 1")
        self.le2 = LegalEntity.objects.create(name="LE 2")
        self.unit1 = OrgUnit.objects.create(name="Unit 1", legal_entity=self.le1)
        self.unit2 = OrgUnit.objects.create(name="Unit 2", legal_entity=self.le2)
        self.actor = Employee.objects.create(first_name="Actor", legal_entity=self.le1, org_unit=self.unit1)
        self.same = Employee.objects.create(first_name="Same", legal_entity=self.le1, org_unit=self.unit1)
        self.other = Employee.objects.create(first_name="Other", legal_entity=self.le2, org_unit=self.unit2)
        self.permission = Permission.objects.create(code="employee.view", name="View")

    def grant(self, scope, **kwargs):
        role = Role.objects.create(code=f"role-{scope}-{Role.objects.count()}", name="Role")
        RolePermission.objects.create(role=role, permission=self.permission, scope=scope)
        return EmployeeRole.objects.create(employee=self.actor, role=role, **kwargs)

    def test_global_legal_entity_org_unit_and_own_scopes(self):
        self.grant(Scope.LEGAL_ENTITY, legal_entity=self.le1)
        self.assertTrue(PermissionService.has_permission(employee=self.actor, permission="employee.view", obj=self.same))
        self.assertFalse(PermissionService.has_permission(employee=self.actor, permission="employee.view", obj=self.other))
        self.grant(Scope.GLOBAL)
        self.assertTrue(PermissionService.has_permission(employee=self.actor, permission="employee.view", obj=self.other))

    def test_missing_inactive_and_expired_roles_are_denied(self):
        self.assertFalse(PermissionService.has_permission(employee=self.actor, permission="employee.view", obj=self.actor))
        assignment = self.grant(Scope.OWN)
        self.assertTrue(PermissionService.has_permission(employee=self.actor, permission="employee.view", obj=self.actor))
        assignment.active_until = timezone.now() - timedelta(seconds=1)
        assignment.save(update_fields=["active_until"])
        self.assertFalse(PermissionService.has_permission(employee=self.actor, permission="employee.view", obj=self.actor))

    def test_inactive_employee_cannot_use_permission(self):
        self.grant(Scope.GLOBAL)
        self.actor.is_active = False
        self.actor.save(update_fields=["is_active"])
        self.assertFalse(PermissionService.has_permission(employee=self.actor, permission="employee.view", obj=self.other))
