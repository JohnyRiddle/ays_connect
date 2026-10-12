from rest_framework.test import APITestCase

from accounts.models import User
from employees.models import AssignmentTarget, Employee


class AssignmentTargetLookupApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username="target-admin", email="target-admin@example.test", password="pass")
        self.employee = Employee.objects.create(first_name="Иван", last_name="Исполнитель", employee_number="TARGET-1")
        self.target = AssignmentTarget.objects.create(target_type=AssignmentTarget.Type.EMPLOYEE, employee=self.employee)
        self.client.force_authenticate(self.user)

    def test_lookup_returns_canonical_id_type_and_display_name(self):
        response = self.client.get("/api/internal/v1/assignment-targets/?search=Исполнитель")
        self.assertEqual(response.status_code, 200)
        item = response.data["results"][0]
        self.assertEqual(item["id"], str(self.target.pk))
        self.assertEqual(item["target_type"], "employee")
        self.assertIn("Исполнитель", item["display_name"])

    def test_lookup_is_read_only(self):
        response = self.client.post("/api/internal/v1/assignment-targets/", {"target_type": "employee", "employee": str(self.employee.pk)})
        self.assertEqual(response.status_code, 405)

    def test_new_employee_service_is_selectable_without_manual_target_creation(self):
        from employees.services import EmployeeService
        employee = EmployeeService.create(actor_user=self.user, first_name="Новый", last_name="Выбираемый")
        response = self.client.get("/api/internal/v1/assignment-targets/?search=Выбираемый")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(str(response.data["results"][0]["employee"]), str(employee.pk))

    def test_backfill_preview_apply_and_replay_preserve_existing_targets(self):
        from django.core.management import call_command
        from employees.services import EmployeeAssignmentTargetService
        from audit.models import AuditEvent
        existing = self.target.pk
        missing = Employee.objects.create(first_name="Missing")
        inactive = Employee.objects.create(first_name="Inactive", is_active=False)
        call_command("ensure_employee_assignment_targets")
        self.assertFalse(missing.assignment_targets.exists())
        call_command("ensure_employee_assignment_targets", apply=True, actor_id=self.user.pk)
        target = missing.assignment_targets.get()
        self.assertTrue(AssignmentTarget.objects.filter(pk=existing).exists())
        self.assertFalse(inactive.assignment_targets.exists())
        call_command("ensure_employee_assignment_targets", apply=True, actor_id=self.user.pk)
        same, created = EmployeeAssignmentTargetService.ensure(employee=missing, actor_user=self.user)
        self.assertFalse(created)
        self.assertEqual(same.pk, target.pk)
        self.assertEqual(missing.assignment_targets.count(), 1)
        self.assertTrue(AuditEvent.objects.filter(action="assignment_target.created", entity_id=str(target.pk)).exists())

    def test_apply_requires_authorized_actor(self):
        from django.core.management import call_command
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError):
            call_command("ensure_employee_assignment_targets", apply=True)

    def test_scoped_lookup_detail_search_counts_never_expose_foreign_employee(self):
        from organizations.models import Location
        from access_control.models import Role, Permission, RolePermission, EmployeeRole
        from employees.services import EmployeeAssignmentTargetService
        from employees.models import Position
        a=Location.objects.create(name="Scope A")
        b=Location.objects.create(name="Scope B")
        self.employee.primary_location=a;self.employee.save(update_fields=["primary_location"])
        foreign=Employee.objects.create(first_name="Hidden foreign",primary_location=b)
        target,_=EmployeeAssignmentTargetService.ensure(employee=foreign,actor_user=self.user)
        reader=User.objects.create_user(username="scoped-reader",email="scoped-reader@synthetic.test")
        actor=Employee.objects.create(user=reader,first_name="Reader",primary_location=a)
        role=Role.objects.create(code="scoped-assignment-reader",name="Scoped reader")
        permission,_=Permission.objects.get_or_create(code="employee.view",defaults={"name":"Employee view"})
        RolePermission.objects.create(role=role,permission=permission,scope="location")
        EmployeeRole.objects.create(employee=actor,role=role,location=a)
        position=Position.objects.create(name="Hidden aggregate")
        aggregate=AssignmentTarget.objects.create(target_type="position",position=position)
        self.client.force_authenticate(reader)
        response=self.client.get("/api/internal/v1/assignment-targets/")
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.data["count"],1)
        self.assertEqual(response.data["results"][0]["id"],str(self.target.pk))
        self.assertEqual(self.client.get(f"/api/internal/v1/assignment-targets/{target.pk}/").status_code,404)
        self.assertEqual(self.client.get(f"/api/internal/v1/assignment-targets/{aggregate.pk}/").status_code,404)
        self.assertEqual(self.client.get("/api/internal/v1/assignment-targets/?search=Hidden").data["count"],0)
        self.assertEqual(self.client.get("/api/internal/v1/assignment-targets/?target_type=position").data["count"],0)
        EmployeeRole.objects.filter(employee=actor).update(is_active=False)
        self.assertEqual(self.client.get("/api/internal/v1/assignment-targets/").status_code,403)

    def test_inactive_employee_excluded_without_rewriting_historical_task(self):
        from employees.services import EmployeeService
        from employees.assignment import AssignmentResolver,AssignmentTargetUnresolved
        from work_tasks.models import Task
        task=Task.objects.create(number="TARGET-HISTORY",title="History",author=self.employee,
            responsible_target=self.target,responsible_employee=self.employee,created_by=self.user,updated_by=self.user)
        EmployeeService.deactivate(employee=self.employee,actor_user=self.user)
        self.assertEqual(self.client.get("/api/internal/v1/assignment-targets/").data["count"],0)
        self.assertEqual(self.client.get(f"/api/internal/v1/assignment-targets/{self.target.pk}/").status_code,404)
        with self.assertRaises(AssignmentTargetUnresolved):AssignmentResolver.resolve(self.target)
        task.refresh_from_db()
        self.assertEqual(task.responsible_target_id,self.target.pk)
        self.assertEqual(task.responsible_employee_id,self.employee.pk)
        self.assertTrue(AssignmentTarget.objects.filter(pk=self.target.pk).exists())

    def test_onboarding_and_blocked_account_cannot_be_new_executor(self):
        from employees.services import EmployeeService,EmployeeAssignmentTargetService
        person=EmployeeService.create(actor_user=self.user,first_name="Pending",status="onboarding")
        self.assertFalse(person.assignment_targets.exists())
        user=User.objects.create_user(username="blocked-target",email="blocked-target@synthetic.test",is_active=False)
        person=Employee.objects.create(user=user,first_name="Blocked")
        self.assertEqual(EmployeeAssignmentTargetService.ensure(employee=person,actor_user=self.user),(None,False))
        self.assertEqual(self.client.get("/api/internal/v1/assignment-targets/").data["count"],1)


from django.test import TransactionTestCase
from concurrent.futures import ThreadPoolExecutor
from django.db import connection,close_old_connections


class ConcurrentAssignmentTargetTests(TransactionTestCase):
    def test_parallel_ensure_reuses_one_target_and_audit_event(self):
        from employees.services import EmployeeAssignmentTargetService
        from audit.models import AuditEvent
        from events.models import OutboxEvent
        employee=Employee.objects.create(first_name="Concurrent target")
        def create(_):
            close_old_connections()
            try:
                target,created=EmployeeAssignmentTargetService.ensure(employee=employee)
                return target.pk
            finally:connection.close()
        with ThreadPoolExecutor(max_workers=2) as pool:ids=list(pool.map(create,range(2)))
        self.assertEqual(ids[0],ids[1])
        self.assertEqual(employee.assignment_targets.count(),1)
        self.assertEqual(AuditEvent.objects.filter(action="assignment_target.created",entity_id=str(ids[0])).count(),1)
        self.assertEqual(OutboxEvent.objects.filter(event_type="assignment_target.created",entity_id=str(ids[0])).count(),1)
