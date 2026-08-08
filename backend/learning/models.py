from django.conf import settings
from django.db import models


class CourseCategory(models.Model):
    name = models.CharField(max_length=180)
    slug = models.SlugField(max_length=190, unique=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="children")
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "Категории курсов"

    def __str__(self):
        return self.name


class Course(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Черновик"
        REVIEW = "REVIEW", "На проверке"
        PUBLISHED = "PUBLISHED", "Опубликован"
        ARCHIVED = "ARCHIVED", "Архив"

    title = models.CharField(max_length=240)
    slug = models.SlugField(max_length=250, unique=True)
    description = models.TextField(blank=True)
    short_description = models.CharField(max_length=360, blank=True)
    category = models.ForeignKey(CourseCategory, on_delete=models.PROTECT, related_name="courses")
    cover_image = models.FileField(upload_to="learning/covers/%Y/%m/", blank=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="authored_courses")
    owner_department = models.ForeignKey("organizations.Department", on_delete=models.SET_NULL, null=True, blank=True, related_name="courses")
    is_mandatory = models.BooleanField(default=False)
    estimated_duration_minutes = models.PositiveIntegerField(default=0)
    passing_score = models.PositiveSmallIntegerField(default=80)
    max_attempts = models.PositiveSmallIntegerField(default=3)
    certificate_enabled = models.BooleanField(default=False)
    certificate_validity_days = models.PositiveIntegerField(null=True, blank=True)
    repeat_after_days = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    version = models.PositiveIntegerField(default=1)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title


class CourseAudience(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="audience_rules")
    employee = models.ForeignKey("employees.Employee", on_delete=models.CASCADE, null=True, blank=True, related_name="course_audience_rules")
    role = models.ForeignKey("accounts.Role", on_delete=models.CASCADE, null=True, blank=True, related_name="course_audience_rules")
    department = models.ForeignKey("organizations.Department", on_delete=models.CASCADE, null=True, blank=True, related_name="course_audience_rules")
    facility = models.ForeignKey("organizations.Facility", on_delete=models.CASCADE, null=True, blank=True, related_name="course_audience_rules")
    position = models.CharField(max_length=150, blank=True)
    region = models.ForeignKey("organizations.Region", on_delete=models.CASCADE, null=True, blank=True, related_name="course_audience_rules")
    is_required = models.BooleanField(default=True)


class CourseModule(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="modules")
    title = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_required = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.course}: {self.title}"


class Lesson(models.Model):
    class Type(models.TextChoices):
        TEXT = "TEXT", "Текст"
        VIDEO = "VIDEO", "Видео"
        DOCUMENT = "DOCUMENT", "Документ"
        PRESENTATION = "PRESENTATION", "Презентация"
        IMAGE = "IMAGE", "Изображение"
        EXTERNAL_LINK = "EXTERNAL_LINK", "Внешняя ссылка"
        PRACTICAL_TASK = "PRACTICAL_TASK", "Практическое задание"
        ASSESSMENT = "ASSESSMENT", "Тестирование"

    module = models.ForeignKey(CourseModule, on_delete=models.CASCADE, related_name="lessons")
    title = models.CharField(max_length=240)
    lesson_type = models.CharField(max_length=24, choices=Type.choices)
    content = models.TextField(blank=True)
    material = models.ForeignKey("knowledge_base.KnowledgeMaterial", on_delete=models.SET_NULL, null=True, blank=True, related_name="lessons")
    video_url = models.URLField(blank=True)
    estimated_duration_minutes = models.PositiveIntegerField(default=0)
    sort_order = models.PositiveIntegerField(default=0)
    is_required = models.BooleanField(default=True)
    requires_confirmation = models.BooleanField(default=False)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.title


class CourseAssignment(models.Model):
    class Status(models.TextChoices):
        ASSIGNED = "ASSIGNED", "Назначено"
        NOT_STARTED = "NOT_STARTED", "Не начато"
        IN_PROGRESS = "IN_PROGRESS", "В процессе"
        WAITING_ASSESSMENT = "WAITING_ASSESSMENT", "Ожидает тестирования"
        COMPLETED = "COMPLETED", "Завершено"
        FAILED = "FAILED", "Не пройдено"
        OVERDUE = "OVERDUE", "Просрочено"
        CANCELLED = "CANCELLED", "Отменено"
        EXPIRED = "EXPIRED", "Истёк срок"

    class Source(models.TextChoices):
        MANUAL = "MANUAL", "Вручную"
        ROLE_RULE = "ROLE_RULE", "По роли"
        POSITION_RULE = "POSITION_RULE", "По должности"
        DEPARTMENT_RULE = "DEPARTMENT_RULE", "По подразделению"
        ONBOARDING = "ONBOARDING", "Адаптация"
        INCIDENT = "INCIDENT", "Инцидент"
        HACCP_VIOLATION = "HACCP_VIOLATION", "Нарушение ХАССП"
        CHECKLIST_VIOLATION = "CHECKLIST_VIOLATION", "Нарушение чек-листа"
        DOCUMENT_UPDATE = "DOCUMENT_UPDATE", "Обновление документа"
        CERTIFICATE_EXPIRATION = "CERTIFICATE_EXPIRATION", "Истечение допуска"
        SCHEDULE = "SCHEDULE", "Расписание"

    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="assignments")
    employee = models.ForeignKey("employees.Employee", on_delete=models.CASCADE, related_name="course_assignments")
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="assigned_courses")
    assigned_at = models.DateTimeField(auto_now_add=True)
    due_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.ASSIGNED)
    progress_percent = models.PositiveSmallIntegerField(default=0)
    current_lesson = models.ForeignKey(Lesson, on_delete=models.SET_NULL, null=True, blank=True, related_name="current_for_assignments")
    is_mandatory = models.BooleanField(default=True)
    source = models.CharField(max_length=30, choices=Source.choices, default=Source.MANUAL)
    related_task = models.ForeignKey("tasks.Task", on_delete=models.SET_NULL, null=True, blank=True, related_name="course_assignments")
    related_incident = models.ForeignKey("incidents.Incident", on_delete=models.SET_NULL, null=True, blank=True, related_name="course_assignments")
    related_checklist = models.ForeignKey("checklists.ChecklistRun", on_delete=models.SET_NULL, null=True, blank=True, related_name="course_assignments")
    comment = models.TextField(blank=True)

    class Meta:
        ordering = ["due_at", "-assigned_at"]


class LessonProgress(models.Model):
    assignment = models.ForeignKey(CourseAssignment, on_delete=models.CASCADE, related_name="lesson_progress")
    lesson = models.ForeignKey(Lesson, on_delete=models.PROTECT, related_name="progress_records")
    opened_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    progress_percent = models.PositiveSmallIntegerField(default=0)
    confirmed = models.BooleanField(default=False)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    time_spent_seconds = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["assignment", "lesson"], name="unique_assignment_lesson_progress")]


class Assessment(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="assessments")
    title = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    time_limit_minutes = models.PositiveIntegerField(default=30)
    passing_score = models.PositiveSmallIntegerField(default=80)
    max_attempts = models.PositiveSmallIntegerField(default=3)
    shuffle_questions = models.BooleanField(default=True)
    shuffle_answers = models.BooleanField(default=True)
    questions_per_attempt = models.PositiveIntegerField(null=True, blank=True)
    show_correct_answers = models.BooleanField(default=False)
    allow_review = models.BooleanField(default=True)
    manual_review_required = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.title


class Question(models.Model):
    class Type(models.TextChoices):
        SINGLE_CHOICE = "SINGLE_CHOICE", "Один вариант"
        MULTIPLE_CHOICE = "MULTIPLE_CHOICE", "Несколько вариантов"
        TRUE_FALSE = "TRUE_FALSE", "Да/нет"
        TEXT = "TEXT", "Текст"
        NUMBER = "NUMBER", "Число"
        MATCHING = "MATCHING", "Соответствие"
        ORDERING = "ORDERING", "Порядок"
        IMAGE_CHOICE = "IMAGE_CHOICE", "Выбор изображения"
        CASE_STUDY = "CASE_STUDY", "Ситуационная задача"

    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="questions")
    text = models.TextField()
    question_type = models.CharField(max_length=24, choices=Type.choices)
    explanation = models.TextField(blank=True)
    image = models.FileField(upload_to="learning/questions/%Y/%m/", blank=True)
    points = models.DecimalField(max_digits=7, decimal_places=2, default=1)
    sort_order = models.PositiveIntegerField(default=0)
    is_required = models.BooleanField(default=True)
    manual_review_required = models.BooleanField(default=False)

    class Meta:
        ordering = ["sort_order", "id"]


class AnswerOption(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="options")
    text = models.CharField(max_length=500, blank=True)
    image = models.FileField(upload_to="learning/answers/%Y/%m/", blank=True)
    is_correct = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    match_key = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["sort_order", "id"]


class AssessmentAttempt(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = "IN_PROGRESS", "В процессе"
        SUBMITTED = "SUBMITTED", "Отправлено"
        AUTO_GRADED = "AUTO_GRADED", "Проверено автоматически"
        WAITING_REVIEW = "WAITING_REVIEW", "Ожидает проверки"
        PASSED = "PASSED", "Пройдено"
        FAILED = "FAILED", "Не пройдено"
        EXPIRED = "EXPIRED", "Время истекло"

    assessment = models.ForeignKey(Assessment, on_delete=models.PROTECT, related_name="attempts")
    assignment = models.ForeignKey(CourseAssignment, on_delete=models.CASCADE, related_name="assessment_attempts")
    employee = models.ForeignKey("employees.Employee", on_delete=models.CASCADE, related_name="assessment_attempts")
    questions = models.ManyToManyField(Question, related_name="attempts")
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.IN_PROGRESS)
    score = models.DecimalField(max_digits=9, decimal_places=2, default=0)
    max_score = models.DecimalField(max_digits=9, decimal_places=2, default=0)
    score_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    passed = models.BooleanField(default=False)
    attempt_number = models.PositiveSmallIntegerField()
    time_spent_seconds = models.PositiveIntegerField(default=0)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_assessment_attempts")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_comment = models.TextField(blank=True)

    class Meta:
        ordering = ["-started_at"]
        constraints = [models.UniqueConstraint(fields=["assessment", "employee", "attempt_number"], name="unique_assessment_employee_attempt_number")]


class AssessmentResponse(models.Model):
    attempt = models.ForeignKey(AssessmentAttempt, on_delete=models.CASCADE, related_name="responses")
    question = models.ForeignKey(Question, on_delete=models.PROTECT, related_name="responses")
    selected_options = models.ManyToManyField(AnswerOption, blank=True, related_name="responses")
    text_answer = models.TextField(blank=True)
    number_answer = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    is_correct = models.BooleanField(null=True, blank=True)
    points_awarded = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    review_comment = models.TextField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["attempt", "question"], name="unique_attempt_question_response")]


class Certificate(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Действует"
        EXPIRING = "EXPIRING", "Истекает"
        EXPIRED = "EXPIRED", "Истёк"
        REVOKED = "REVOKED", "Отозван"

    employee = models.ForeignKey("employees.Employee", on_delete=models.CASCADE, related_name="certificates")
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="certificates")
    assignment = models.OneToOneField(CourseAssignment, on_delete=models.PROTECT, related_name="certificate")
    certificate_number = models.CharField(max_length=64, unique=True)
    issued_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    file = models.FileField(upload_to="learning/certificates/%Y/%m/", blank=True)
    verification_code = models.CharField(max_length=64, unique=True)
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="issued_certificates")
