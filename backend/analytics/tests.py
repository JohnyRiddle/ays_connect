from datetime import date,timedelta
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from accounts.models import Role,User,UserRole
from employees.models import Employee
from organizations.models import Company,Department
from tasks.models import Task
from learning.models import Course,CourseAssignment,CourseCategory
from knowledge_base.models import KnowledgeCategory,KnowledgeMaterial,MaterialAcknowledgmentAssignment,MaterialVersion
class AnalyticsTests(TestCase):
    def setUp(self):
        self.company=Company.objects.create(name="Тест",short_name="Т");dep=Department.objects.create(company=self.company,name="Отдел")
        self.user=User.objects.create_user(username="worker",email="worker@analytics.test",password="pass12345",first_name="Иван",last_name="Тестов");self.employee=Employee.objects.create(user=self.user,company=self.company,department=dep,employee_number="A1",position="Специалист",hire_date=date.today())
        deadline=timezone.now()+timedelta(days=1);Task.objects.create(title="Готово",creator=self.user,assignee=self.user,status=Task.Status.CLOSED,initial_deadline=deadline,deadline=deadline,completed_at=timezone.now())
        self.client=APIClient();self.client.force_authenticate(self.user)
    def test_personal_performance_is_objective(self):
        response=self.client.get("/api/v1/analytics/me/");self.assertEqual(response.status_code,200);self.assertEqual(response.data["timeliness"],100);self.assertEqual(response.data["completed_tasks"],1)
        self.assertEqual(response.data["mandatory_learning_on_time"],100.0);self.assertEqual(response.data["acknowledgment_rate"],100.0)
    def test_employee_cannot_open_management_dashboard(self):
        self.assertEqual(self.client.get("/api/v1/analytics/management/").status_code,403)
    def test_manager_sees_company_dashboard(self):
        role=Role.objects.create(code=Role.Code.MANAGER,name="Руководитель");UserRole.objects.create(user=self.user,role=role,company=self.company)
        response=self.client.get("/api/v1/analytics/management/");self.assertEqual(response.status_code,200);self.assertEqual(response.data["summary"]["employee_count"],1)
