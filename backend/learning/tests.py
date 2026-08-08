from datetime import date, timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Role, User, UserRole
from employees.models import Employee
from organizations.models import Company, Department
from audit.models import AuditEvent
from .models import AnswerOption, Assessment, AssessmentAttempt, Certificate, Course, CourseAssignment, CourseCategory, CourseModule, Lesson, LessonProgress, Question


class LearningApiTests(APITestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Компания", short_name="Тест")
        self.department = Department.objects.create(company=self.company, name="Операции")
        self.manager = User.objects.create_user(username="manager-learning", email="manager-learning@example.com", password="Pass12345!")
        self.worker = User.objects.create_user(username="worker-learning", email="worker-learning@example.com", password="Pass12345!")
        manager_role = Role.objects.create(code=Role.Code.MANAGER, name="Руководитель")
        employee_role = Role.objects.create(code=Role.Code.EMPLOYEE, name="Сотрудник")
        UserRole.objects.create(user=self.manager, role=manager_role, company=self.company)
        UserRole.objects.create(user=self.worker, role=employee_role, company=self.company)
        self.employee = Employee.objects.create(user=self.worker, company=self.company, department=self.department, employee_number="L-1", position="Специалист", hire_date=date(2024, 1, 1))
        self.category = CourseCategory.objects.create(name="Охрана труда", slug="safety")

    def authenticate(self, user):
        self.client.force_authenticate(user)

    def build_course(self):
        course = Course.objects.create(title="Безопасная работа", slug="safe-work", category=self.category, author=self.manager, owner_department=self.department)
        module = CourseModule.objects.create(course=course, title="Основы", sort_order=1)
        lesson1 = Lesson.objects.create(module=module, title="Введение", lesson_type=Lesson.Type.TEXT, content="Текст", sort_order=1)
        lesson2 = Lesson.objects.create(module=module, title="Подтверждение", lesson_type=Lesson.Type.TEXT, requires_confirmation=True, sort_order=2)
        return course, lesson1, lesson2

    def publish(self, course):
        self.authenticate(self.manager)
        return self.client.post(f"/api/v1/learning/courses/{course.id}/publish/")

    def assign(self, course):
        self.authenticate(self.manager)
        return self.client.post("/api/v1/learning/assignments/", {"course": course.id, "employee": self.employee.id, "due_at": (timezone.now() + timedelta(days=5)).isoformat(), "is_mandatory": True, "source": "MANUAL"}, format="json")

    def test_manager_creates_course_employee_cannot(self):
        self.authenticate(self.manager)
        response = self.client.post("/api/v1/learning/courses/", {"title": "Курс", "slug": "course", "category": self.category.id, "description": "Описание"})
        self.assertEqual(response.status_code, 201)
        self.authenticate(self.worker)
        denied = self.client.post("/api/v1/learning/courses/", {"title": "Другой", "slug": "other", "category": self.category.id})
        self.assertEqual(denied.status_code, 403)

    def test_publish_requires_lesson_and_writes_audit(self):
        empty = Course.objects.create(title="Пустой", slug="empty", category=self.category, author=self.manager)
        self.authenticate(self.manager)
        self.assertEqual(self.client.post(f"/api/v1/learning/courses/{empty.id}/publish/").status_code, 400)
        course, _, _ = self.build_course()
        response = self.publish(course)
        self.assertEqual(response.status_code, 200)
        course.refresh_from_db()
        self.assertEqual(course.status, Course.Status.PUBLISHED)
        self.assertTrue(AuditEvent.objects.filter(action="learning.course_published", entity_id=str(course.id)).exists())

    def test_assignment_only_for_published_course(self):
        course, _, _ = self.build_course()
        self.assertEqual(self.assign(course).status_code, 400)
        self.publish(course)
        response = self.assign(course)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], CourseAssignment.Status.ASSIGNED)

    def test_employee_sees_only_own_assignment_and_starts(self):
        course, lesson1, _ = self.build_course(); self.publish(course)
        assignment_id = self.assign(course).data["id"]
        self.authenticate(self.worker)
        mine = self.client.get("/api/v1/learning/assignments/my/")
        self.assertEqual(len(mine.data), 1)
        started = self.client.post(f"/api/v1/learning/assignments/{assignment_id}/start/")
        self.assertEqual(started.status_code, 200)
        self.assertEqual(started.data["status"], CourseAssignment.Status.IN_PROGRESS)
        self.assertEqual(started.data["current_lesson"], lesson1.id)

    def test_progress_and_course_completion_are_calculated(self):
        course, lesson1, lesson2 = self.build_course(); self.publish(course)
        assignment_id = self.assign(course).data["id"]
        self.authenticate(self.worker)
        self.client.post(f"/api/v1/learning/assignments/{assignment_id}/start/")
        first = self.client.post(f"/api/v1/learning/lessons/{lesson1.id}/complete/", {"assignment": assignment_id, "time_spent_seconds": 120}, format="json")
        self.assertEqual(first.data["assignment"]["progress_percent"], 50)
        denied = self.client.post(f"/api/v1/learning/lessons/{lesson2.id}/complete/", {"assignment": assignment_id}, format="json")
        self.assertEqual(denied.status_code, 400)
        second = self.client.post(f"/api/v1/learning/lessons/{lesson2.id}/complete/", {"assignment": assignment_id, "confirmed": True}, format="json")
        self.assertEqual(second.data["assignment"]["progress_percent"], 100)
        self.assertEqual(second.data["assignment"]["status"], CourseAssignment.Status.COMPLETED)
        self.assertEqual(LessonProgress.objects.filter(assignment_id=assignment_id, completed_at__isnull=False).count(), 2)

    def test_employee_cannot_complete_another_assignment(self):
        course, lesson1, _ = self.build_course(); self.publish(course)
        assignment_id = self.assign(course).data["id"]
        other = User.objects.create_user(username="other-learning", email="other-learning@example.com", password="Pass12345!")
        self.authenticate(other)
        response = self.client.post(f"/api/v1/learning/lessons/{lesson1.id}/complete/", {"assignment": assignment_id}, format="json")
        self.assertEqual(response.status_code, 404)


class AssessmentApiTests(APITestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Компания", short_name="Оценка")
        self.department = Department.objects.create(company=self.company, name="Обучение")
        self.manager = User.objects.create_user(username="assessment-manager", email="assessment-manager@example.com", password="Pass12345!")
        self.worker = User.objects.create_user(username="assessment-worker", email="assessment-worker@example.com", password="Pass12345!")
        manager_role = Role.objects.create(code=Role.Code.MANAGER, name="Руководитель")
        employee_role = Role.objects.create(code=Role.Code.EMPLOYEE, name="Сотрудник")
        UserRole.objects.create(user=self.manager, role=manager_role, company=self.company)
        UserRole.objects.create(user=self.worker, role=employee_role, company=self.company)
        self.employee = Employee.objects.create(user=self.worker, company=self.company, department=self.department, employee_number="A-1", position="Специалист", hire_date=date(2024, 1, 1))
        category = CourseCategory.objects.create(name="Контроль", slug="control")
        self.course = Course.objects.create(title="Контроль знаний", slug="knowledge-control", category=category, author=self.manager, status=Course.Status.PUBLISHED, max_attempts=2, certificate_enabled=True, certificate_validity_days=365)
        module = CourseModule.objects.create(course=self.course, title="Материал")
        self.lesson = Lesson.objects.create(module=module, title="Урок", lesson_type=Lesson.Type.TEXT)
        self.assignment = CourseAssignment.objects.create(course=self.course, employee=self.employee, assigned_by=self.manager, status=CourseAssignment.Status.WAITING_ASSESSMENT, progress_percent=100)
        self.assessment = Assessment.objects.create(course=self.course, title="Итоговый тест", passing_score=70, max_attempts=2, shuffle_questions=False)
        self.question = Question.objects.create(assessment=self.assessment, text="Норма?", question_type=Question.Type.SINGLE_CHOICE, points=2)
        self.correct = AnswerOption.objects.create(question=self.question, text="Да", is_correct=True)
        self.wrong = AnswerOption.objects.create(question=self.question, text="Нет", is_correct=False)

    def authenticate(self, user):
        self.client.force_authenticate(user)

    def start(self):
        self.authenticate(self.worker)
        return self.client.post(f"/api/v1/learning/assessments/{self.assessment.id}/start/", {"assignment": self.assignment.id}, format="json")

    def submit(self, attempt_id, option_id):
        return self.client.post(f"/api/v1/learning/attempts/{attempt_id}/submit/", {"answers": [{"question": self.question.id, "selected_options": [option_id]}]}, format="json")

    def test_attempt_does_not_reveal_correct_answers(self):
        response = self.start()
        self.assertEqual(response.status_code, 201)
        option = response.data["questions"][0]["options"][0]
        self.assertNotIn("is_correct", option)

    def test_correct_answer_passes_and_issues_certificate(self):
        attempt = self.start()
        result = self.submit(attempt.data["id"], self.correct.id)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data["status"], AssessmentAttempt.Status.PASSED)
        self.assertEqual(result.data["score_percent"], "100.00")
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.status, CourseAssignment.Status.COMPLETED)
        self.assertTrue(Certificate.objects.filter(assignment=self.assignment).exists())

    def test_failed_attempt_allows_retry_then_enforces_limit(self):
        first = self.start(); failed1 = self.submit(first.data["id"], self.wrong.id)
        self.assertEqual(failed1.data["status"], AssessmentAttempt.Status.FAILED)
        second = self.start(); failed2 = self.submit(second.data["id"], self.wrong.id)
        self.assertEqual(failed2.data["status"], AssessmentAttempt.Status.FAILED)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.status, CourseAssignment.Status.FAILED)
        third = self.start()
        self.assertEqual(third.status_code, 400)

    def test_required_empty_submission_is_rejected(self):
        attempt = self.start()
        response = self.client.post(f"/api/v1/learning/attempts/{attempt.data['id']}/submit/", {"answers": []}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_foreign_option_is_rejected(self):
        other_question = Question.objects.create(assessment=self.assessment, text="Другой", question_type=Question.Type.SINGLE_CHOICE)
        foreign = AnswerOption.objects.create(question=other_question, text="Чужой", is_correct=True)
        attempt = self.start()
        response = self.submit(attempt.data["id"], foreign.id)
        self.assertEqual(response.status_code, 400)

    def test_text_answer_waits_for_manual_review(self):
        self.question.question_type = Question.Type.TEXT
        self.question.manual_review_required = True
        self.question.save(update_fields=["question_type", "manual_review_required"])
        attempt = self.start()
        submitted = self.client.post(f"/api/v1/learning/attempts/{attempt.data['id']}/submit/", {"answers": [{"question": self.question.id, "text_answer": "Развёрнутый ответ"}]}, format="json")
        self.assertEqual(submitted.data["status"], AssessmentAttempt.Status.WAITING_REVIEW)
        response_id = submitted.data["responses"][0]["id"]
        self.authenticate(self.manager)
        reviewed = self.client.post(f"/api/v1/learning/attempts/{attempt.data['id']}/review/", {"reviews": [{"response": response_id, "points_awarded": 2, "comment": "Верно"}]}, format="json")
        self.assertEqual(reviewed.status_code, 200)
        self.assertEqual(reviewed.data["status"], AssessmentAttempt.Status.PASSED)
