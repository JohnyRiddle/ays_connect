from concurrent.futures import ThreadPoolExecutor

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, close_old_connections, connection, connections, transaction
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient

from audit.models import AuditEvent
from events.models import OutboxEvent
from organizations.models import LegalEntity, Location, OrgUnit
from .models import Employee, EmployeeAssignment, EmployeeInvitation, EmployeeManagerAssignment, FunctionalGroup, Position
from .onboarding import InvitationService
from .services import EmployeeAssignmentService, EmployeeManagerService, EmployeeService, FunctionalGroupService


class PeoplePhase21DomainTests(TestCase):
    def setUp(self):
        self.legal_entity = LegalEntity.objects.create(name="AYS Test")
        self.org_unit = OrgUnit.objects.create(name="IT", legal_entity=self.legal_entity)
        self.location = Location.objects.create(name="Новосибирск", legal_entity=self.legal_entity)
        self.position = Position.objects.create(name="Инженер", legal_entity=self.legal_entity, org_unit=self.org_unit)

    def employee(self, name="Иван", **kwargs):
        return Employee.objects.create(first_name=name, **kwargs)

    def test_employee_number_is_generated_and_immutable(self):
        first = self.employee()
        second = self.employee("Пётр")
        self.assertRegex(first.employee_number, r"^EMP-\d{6}$")
        self.assertNotEqual(first.employee_number, second.employee_number)
        first.employee_number = "EMP-999999"
        with self.assertRaises(ValidationError):
            first.save()

    def test_multiple_assignments_and_primary_invariant(self):
        employee = self.employee()
        primary = EmployeeAssignmentService.start(
            employee=employee, position=self.position, org_unit=self.org_unit,
            legal_entity=self.legal_entity, location=self.location, is_primary=True,
        )
        additional = EmployeeAssignmentService.start(employee=employee, legal_entity=self.legal_entity, is_primary=False)
        self.assertTrue(primary.is_primary)
        self.assertFalse(additional.is_primary)
        with self.assertRaises(ValidationError):
            EmployeeAssignmentService.start(employee=employee, is_primary=True)
        employee.refresh_from_db()
        self.assertEqual(employee.position_ref, self.position)
        self.assertEqual(employee.primary_location, self.location)
        replacement = EmployeeAssignmentService.replace_primary(employee=employee, org_unit=self.org_unit)
        primary.refresh_from_db()
        self.assertEqual(primary.status, EmployeeAssignment.Status.ENDED)
        self.assertTrue(replacement.is_primary)

    def test_database_rejects_second_active_primary_assignment(self):
        employee = self.employee()
        EmployeeAssignment.objects.create(employee=employee, is_primary=True)
        with self.assertRaises(IntegrityError), transaction.atomic():
            EmployeeAssignment.objects.create(employee=employee, is_primary=True)

    def test_manager_history_reports_and_cycle_protection(self):
        a, b, c = self.employee("A"), self.employee("B"), self.employee("C")
        EmployeeManagerService.change(employee=a, manager=b)
        EmployeeManagerService.change(employee=b, manager=c)
        with self.assertRaises(ValidationError):
            EmployeeManagerService.change(employee=c, manager=a)
        EmployeeManagerService.change(employee=a, manager=c)
        history = EmployeeManagerAssignment.objects.filter(employee=a).order_by("valid_from")
        self.assertEqual(history.count(), 2)
        self.assertEqual(history.filter(status="active").get().manager, c)
        self.assertEqual(Employee.objects.get(pk=a.pk).manager, c)
        self.assertEqual(EmployeeManagerService.management_chain(a), [c])
        self.assertEqual(list(EmployeeManagerService.direct_reports(c).order_by("first_name")), [a, b])

    def test_termination_is_atomic_preserves_history_and_reactivation_is_clean(self):
        user = get_user_model().objects.create_user(username="phase2", email="phase2@example.test")
        employee = self.employee(user=user)
        assignment = EmployeeAssignmentService.start(employee=employee, is_primary=True, org_unit=self.org_unit)
        manager = self.employee("Manager")
        EmployeeManagerService.change(employee=employee, manager=manager)
        group = FunctionalGroup.objects.create(name="Operations")
        membership = FunctionalGroupService.add_member(group=group, employee=employee)

        EmployeeService.terminate(employee=employee)
        employee.refresh_from_db(); user.refresh_from_db(); assignment.refresh_from_db(); membership.refresh_from_db()
        self.assertEqual(employee.status, Employee.Status.TERMINATED)
        self.assertFalse(employee.is_active)
        self.assertFalse(user.is_active)
        self.assertEqual(assignment.status, EmployeeAssignment.Status.ENDED)
        self.assertFalse(membership.is_active)
        self.assertTrue(AuditEvent.objects.filter(entity_id=str(employee.pk), action="people.employee.terminated").exists())
        self.assertTrue(OutboxEvent.objects.filter(entity_id=str(employee.pk), event_type="people.employee.terminated").exists())

        EmployeeService.reactivate(employee=employee)
        employee.refresh_from_db(); user.refresh_from_db()
        self.assertTrue(employee.is_active)
        self.assertTrue(user.is_active is False)
        self.assertFalse(EmployeeAssignment.objects.filter(employee=employee, status="active").exists())
        self.assertFalse(EmployeeManagerAssignment.objects.filter(employee=employee, status="active").exists())
        self.assertFalse(employee.functional_group_memberships.filter(is_active=True).exists())

    def test_audit_and_outbox_rollback_with_business_mutation(self):
        counts = (Employee.objects.count(), AuditEvent.objects.count(), OutboxEvent.objects.count())
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                EmployeeService.create(first_name="Rollback")
                raise RuntimeError("rollback")
        self.assertEqual(counts, (Employee.objects.count(), AuditEvent.objects.count(), OutboxEvent.objects.count()))

    def test_people_api_create_assignment_manager_and_lifecycle(self):
        admin = get_user_model().objects.create_superuser(username="people-api", email="people-api@example.test", password="x")
        manager = self.employee("Руководитель")
        client = APIClient(); client.force_authenticate(admin)
        created = client.post("/api/internal/v1/people/employees/", {"first_name": "Новый", "last_name": "Сотрудник"}, format="json")
        self.assertEqual(created.status_code, 201)
        employee_id = created.data["id"]
        self.assertRegex(created.data["employee_number"], r"^EMP-\d{6}$")
        assigned = client.post(f"/api/internal/v1/people/employees/{employee_id}/assignments/", {"org_unit_id": str(self.org_unit.pk), "is_primary": True}, format="json")
        self.assertEqual(assigned.status_code, 201)
        changed = client.post(f"/api/internal/v1/people/employees/{employee_id}/change-manager/", {"manager_id": str(manager.pk)}, format="json")
        self.assertEqual(changed.status_code, 200)
        reports = client.get(f"/api/internal/v1/people/employees/{manager.pk}/reports/")
        self.assertEqual(reports.status_code, 200)
        self.assertEqual(len(reports.data), 1)
        terminated = client.post(f"/api/internal/v1/people/employees/{employee_id}/terminate/", {}, format="json")
        self.assertEqual(terminated.status_code, 200)
        self.assertEqual(terminated.data["status"], Employee.Status.TERMINATED)


class PeoplePhase21PostgreSQLConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL concurrency gate")
        self.employee = Employee.objects.create(first_name="Concurrent")
        self.actor = get_user_model().objects.create_superuser(username="people-pg", email="people-pg@example.test", password="x")

    @staticmethod
    def _create_employee(index):
        close_old_connections()
        try:
            return EmployeeService.create(first_name=f"Worker {index}").employee_number
        finally:
            connections.close_all()

    def test_parallel_employee_number_allocation(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            numbers = list(pool.map(self._create_employee, range(24)))
        self.assertEqual(len(numbers), len(set(numbers)))
        self.assertTrue(all(number.startswith("EMP-") for number in numbers))

    @staticmethod
    def _create_primary(employee_id):
        close_old_connections()
        try:
            try:
                EmployeeAssignmentService.start(employee=Employee.objects.get(pk=employee_id), is_primary=True)
                return "created"
            except (ValidationError, IntegrityError):
                return "rejected"
        finally:
            connections.close_all()

    def test_parallel_primary_assignment_creation(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            outcomes = list(pool.map(self._create_primary, [self.employee.pk] * 4))
        self.assertEqual(outcomes.count("created"), 1)
        self.assertEqual(EmployeeAssignment.objects.filter(employee=self.employee, is_primary=True, status="active").count(), 1)

    @staticmethod
    def _change_manager(employee_id, manager_id):
        close_old_connections()
        try:
            EmployeeManagerService.change(employee=Employee.objects.get(pk=employee_id), manager=Employee.objects.get(pk=manager_id))
            return "changed"
        finally:
            connections.close_all()

    def test_parallel_manager_change_keeps_one_active_relation(self):
        managers = [Employee.objects.create(first_name=f"Manager {index}") for index in range(2)]
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda manager: self._change_manager(self.employee.pk, manager.pk), managers))
        self.assertEqual(outcomes, ["changed", "changed"])
        self.assertEqual(EmployeeManagerAssignment.objects.filter(employee=self.employee, status="active").count(), 1)
        self.assertEqual(EmployeeManagerAssignment.objects.filter(employee=self.employee).count(), 2)

    @staticmethod
    def _terminate_or_assign(operation, employee_id):
        close_old_connections()
        try:
            employee = Employee.objects.get(pk=employee_id)
            try:
                if operation == "terminate":
                    EmployeeService.terminate(employee=employee)
                else:
                    EmployeeAssignmentService.start(employee=employee, is_primary=True)
                return operation
            except ValidationError:
                return "rejected"
        finally:
            connections.close_all()

    def test_termination_vs_assignment_has_no_active_assignment(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda operation: self._terminate_or_assign(operation, self.employee.pk), ["terminate", "assign"]))
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.status, Employee.Status.TERMINATED)
        self.assertFalse(EmployeeAssignment.objects.filter(employee=self.employee, status="active").exists())

    @staticmethod
    def _terminate_or_invite(operation, employee_id, actor_id):
        close_old_connections()
        try:
            employee = Employee.objects.get(pk=employee_id)
            actor = get_user_model().objects.get(pk=actor_id)
            try:
                if operation == "terminate":
                    EmployeeService.terminate(employee=employee, actor_user=actor)
                else:
                    InvitationService.issue(employee=employee, actor_user=actor, delivery_address="race@example.test")
                return operation
            except ValidationError:
                return "rejected"
        finally:
            connections.close_all()

    def test_termination_vs_invitation_leaves_no_open_invitation(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda operation: self._terminate_or_invite(operation, self.employee.pk, self.actor.pk), ["terminate", "invite"]))
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.status, Employee.Status.TERMINATED)
        self.assertFalse(EmployeeInvitation.objects.filter(employee=self.employee, used_at__isnull=True, revoked_at__isnull=True).exists())
