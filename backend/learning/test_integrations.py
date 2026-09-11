from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Role, User, UserRole
from employees.models import Employee
from notifications.models import Notification
from organizations.models import Company, Department
from tasks.models import Task
from .integrations import provision_course_assignment
from .models import Certificate, Course, CourseAssignment, CourseAudience, CourseCategory, CourseModule, Lesson
from .scheduler import process_learning_deadlines
from .services import complete_lesson


class LearningIntegrationTests(TestCase):
    def setUp(self):
        self.company=Company.objects.create(name="Компания",short_name="Инт")
        self.department=Department.objects.create(company=self.company,name="Отдел")
        self.manager=User.objects.create_user(username="integration-manager",email="integration-manager@example.com",password="pass12345")
        self.worker=User.objects.create_user(username="integration-worker",email="integration-worker@example.com",password="pass12345")
        role=Role.objects.create(code=Role.Code.MANAGER,name="Руководитель");UserRole.objects.create(user=self.manager,role=role,company=self.company)
        self.employee=Employee.objects.create(user=self.worker,company=self.company,department=self.department,employee_number="I-1",position="Специалист",hire_date=date.today())
        category=CourseCategory.objects.create(name="Интеграции",slug="integrations")
        self.course=Course.objects.create(title="Интеграционный курс",slug="integration-course",category=category,author=self.manager,status=Course.Status.PUBLISHED)
        module=CourseModule.objects.create(course=self.course,title="Модуль")
        self.lesson=Lesson.objects.create(module=module,title="Урок",lesson_type=Lesson.Type.TEXT)

    def test_assignment_creates_notification_and_optional_task(self):
        assignment=CourseAssignment.objects.create(course=self.course,employee=self.employee,assigned_by=self.manager,due_at=timezone.now()+timedelta(days=2))
        provision_course_assignment(assignment,create_task=True);assignment.refresh_from_db()
        self.assertIsNotNone(assignment.related_task_id)
        self.assertEqual(assignment.related_task.source,Task.Source.TRAINING)
        self.assertTrue(Notification.objects.filter(recipient=self.worker,notification_type=Notification.Type.COURSE_ASSIGNED).exists())

    def test_course_completion_closes_linked_task(self):
        assignment=CourseAssignment.objects.create(course=self.course,employee=self.employee,assigned_by=self.manager,status=CourseAssignment.Status.IN_PROGRESS)
        provision_course_assignment(assignment,create_task=True);assignment.refresh_from_db()
        complete_lesson(assignment=assignment,lesson=self.lesson,actor=self.worker)
        assignment.related_task.refresh_from_db()
        self.assertEqual(assignment.related_task.status,Task.Status.CLOSED)
        self.assertTrue(Notification.objects.filter(notification_type=Notification.Type.COURSE_COMPLETED,entity_id=assignment.id).exists())

    def test_deadline_processing_is_idempotent(self):
        assignment=CourseAssignment.objects.create(course=self.course,employee=self.employee,assigned_by=self.manager,due_at=timezone.now()-timedelta(days=1))
        first=process_learning_deadlines();second=process_learning_deadlines();assignment.refresh_from_db()
        self.assertEqual(assignment.status,CourseAssignment.Status.OVERDUE)
        self.assertEqual(first["courses_overdue"],1);self.assertEqual(second["courses_overdue"],0)
        self.assertEqual(Notification.objects.filter(notification_type=Notification.Type.COURSE_OVERDUE,entity_id=assignment.id).count(),1)

    def test_certificate_status_and_notification(self):
        assignment=CourseAssignment.objects.create(course=self.course,employee=self.employee,assigned_by=self.manager,status=CourseAssignment.Status.COMPLETED)
        certificate=Certificate.objects.create(employee=self.employee,course=self.course,assignment=assignment,certificate_number="TEST-1",verification_code="verify-1",expires_at=timezone.now()+timedelta(days=10),issued_by=self.manager)
        process_learning_deadlines();certificate.refresh_from_db()
        self.assertEqual(certificate.status,Certificate.Status.EXPIRING)
        self.assertTrue(Notification.objects.filter(notification_type=Notification.Type.CERTIFICATE_EXPIRING,entity_id=certificate.id).exists())

    def test_audience_rule_creates_assignment_and_task(self):
        CourseAudience.objects.create(course=self.course, department=self.department, is_required=True)
        result = process_learning_deadlines()
        assignment = CourseAssignment.objects.get(course=self.course, employee=self.employee)
        self.assertEqual(result["audience_assignments"], 1)
        self.assertEqual(assignment.source, CourseAssignment.Source.DEPARTMENT_RULE)
        self.assertIsNotNone(assignment.related_task_id)

    def test_management_learning_endpoints(self):
        CourseAssignment.objects.create(course=self.course, employee=self.employee, assigned_by=self.manager)
        client = APIClient(); client.force_authenticate(self.manager)
        summary = client.get("/api/v1/management/learning/summary/")
        employees = client.get("/api/v1/management/learning/employees/")
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(summary.data["assigned"], 1)
        self.assertEqual(employees.status_code, 200)
        self.assertEqual(employees.data[0]["employee_id"], self.employee.id)
