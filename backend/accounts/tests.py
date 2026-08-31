from datetime import date
from django.test import TestCase
from rest_framework.test import APIClient
from accounts.models import Role, User, UserRole
from employees.models import Employee
from organizations.models import Company, Department
from tasks.models import Task
from django.utils import timezone
from datetime import timedelta

class CoreApiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Тест", short_name="Тест")
        dep = Department.objects.create(company=self.company, name="IT")
        self.user = User.objects.create_user(username="user", email="user@example.test", password="StrongPass123!", first_name="Иван", last_name="Тестов")
        self.employee = Employee.objects.create(user=self.user, company=self.company, department=dep, employee_number="T-1", position="Специалист", hire_date=date.today())
        self.client = APIClient()

    def login(self):
        response = self.client.post("/api/v1/auth/login/", {"email": "user@example.test", "password": "StrongPass123!"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_login_and_profile(self):
        self.login()
        response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["employee"]["position"], "Специалист")

    def test_login_supports_bootstrap_employee_without_legacy_company(self):
        user = User.objects.create_superuser(
            username="pilot-admin",
            email="pilot-admin@example.test",
            password="StrongPilotPass123!",
        )
        Employee.objects.create(user=user, first_name="Pilot", last_name="Admin")

        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": user.email, "password": "StrongPilotPass123!"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["user"]["employee"]["company"])

    def test_employee_cannot_list_all_employees(self):
        role = Role.objects.create(code=Role.Code.EMPLOYEE, name="Сотрудник")
        UserRole.objects.create(user=self.user, role=role, company=self.company)
        self.login()
        self.assertEqual(self.client.get("/api/v1/employees/").status_code, 403)

    def test_manager_can_list_company_employees(self):
        role = Role.objects.create(code=Role.Code.MANAGER, name="Руководитель")
        UserRole.objects.create(user=self.user, role=role, company=self.company)
        self.login()
        response = self.client.get("/api/v1/employees/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

    def test_personal_dashboard_uses_real_tasks(self):
        deadline = timezone.now() + timedelta(hours=2)
        Task.objects.create(title="Реальная задача теста", creator=self.user, assignee=self.user, initial_deadline=deadline, deadline=deadline, status=Task.Status.IN_PROGRESS, priority=Task.Priority.HIGH)
        self.login()
        response = self.client.get("/api/v1/employees/dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["counts"]["active"], 1)
        self.assertEqual(response.data["counts"]["high_priority"], 1)
        self.assertEqual(response.data["today_tasks"][0]["title"], "Реальная задача теста")
