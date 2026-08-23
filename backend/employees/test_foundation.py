from django.db import IntegrityError, transaction
from django.test import TestCase

from audit.models import AuditEvent
from events.models import OutboxEvent
from organizations.models import LegalEntity, OrgUnit
from organizations.services import OrgUnitCycleError, OrgUnitService
from .assignment import AssignmentResolver, AssignmentTargetAmbiguous, AssignmentTargetUnresolved
from .models import AssignmentTarget, Employee, FunctionalGroup, Position
from .services import EmployeeService, FunctionalGroupService


class PeopleFoundationTests(TestCase):
    def setUp(self):
        self.legal_entity = LegalEntity.objects.create(name="ООО Тест")
        self.root = OrgUnitService.create(name="Управление", legal_entity=self.legal_entity)

    def employee(self, **kwargs):
        data = {"first_name": "Иван", "last_name": "Тестов", "legal_entity": self.legal_entity, "org_unit": self.root}
        data.update(kwargs)
        return Employee.objects.create(**data)

    def test_employee_without_user_and_deactivation_preserves_record(self):
        employee = self.employee()
        self.assertIsNone(employee.user)
        EmployeeService.deactivate(employee=employee)
        employee.refresh_from_db()
        self.assertFalse(employee.is_active)
        self.assertEqual(employee.status, Employee.Status.DISMISSED)
        self.assertTrue(Employee.objects.filter(pk=employee.pk).exists())

    def test_org_unit_tree_rejects_self_and_descendant_parent(self):
        child = OrgUnitService.create(name="IT", parent=self.root)
        with self.assertRaises(OrgUnitCycleError):
            OrgUnitService.move(unit=self.root, parent=child)
        with self.assertRaises(OrgUnitCycleError):
            OrgUnitService.move(unit=child, parent=child)

    def test_group_membership_is_deactivated_not_deleted(self):
        employee = self.employee()
        group = FunctionalGroup.objects.create(name="IT Support")
        membership = FunctionalGroupService.add_member(group=group, employee=employee)
        FunctionalGroupService.remove_member(group=group, employee=employee)
        membership.refresh_from_db()
        self.assertFalse(membership.is_active)

    def test_assignment_target_constraint_rejects_multiple_references(self):
        employee = self.employee()
        position = Position.objects.create(name="Специалист")
        with self.assertRaises(IntegrityError), transaction.atomic():
            AssignmentTarget.objects.create(target_type=AssignmentTarget.Type.EMPLOYEE, employee=employee, position=position)

    def test_assignment_resolver_employee_position_and_failures(self):
        employee = self.employee()
        direct = AssignmentTarget.objects.create(target_type=AssignmentTarget.Type.EMPLOYEE, employee=employee)
        self.assertEqual(AssignmentResolver.resolve(direct), [employee])

        position = Position.objects.create(name="Директор")
        position_target = AssignmentTarget.objects.create(target_type=AssignmentTarget.Type.POSITION, position=position)
        with self.assertRaises(AssignmentTargetUnresolved):
            AssignmentResolver.resolve(position_target)
        employee.position_ref = position
        employee.save(update_fields=["position_ref"])
        self.assertEqual(AssignmentResolver.resolve(position_target), [employee])
        self.employee(first_name="Пётр", position_ref=position)
        with self.assertRaises(AssignmentTargetAmbiguous):
            AssignmentResolver.resolve(position_target)

    def test_service_writes_audit_and_outbox_atomically(self):
        employee = EmployeeService.create(first_name="Анна", last_name="Тестова")
        self.assertTrue(AuditEvent.objects.filter(entity_id=str(employee.pk), action="employee.created").exists())
        self.assertTrue(OutboxEvent.objects.filter(entity_id=str(employee.pk), event_type="employee.created").exists())

        count = OutboxEvent.objects.count()
        try:
            with transaction.atomic():
                EmployeeService.create(first_name="Rollback")
                raise RuntimeError("rollback")
        except RuntimeError:
            pass
        self.assertEqual(OutboxEvent.objects.count(), count)
