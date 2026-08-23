import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class TaskStatus(models.TextChoices):
    DRAFT = "draft", "Черновик"
    OPEN = "open", "Открыта"
    IN_PROGRESS = "in_progress", "В работе"
    WAITING = "waiting", "Ожидание"
    REVIEW = "review", "На приёмке"
    COMPLETED = "completed", "Завершена"
    CANCELLED = "cancelled", "Отменена"


class TaskPriority(models.TextChoices):
    LOW = "low", "Низкий"
    NORMAL = "normal", "Обычный"
    HIGH = "high", "Высокий"
    CRITICAL = "critical", "Критический"


class WaitingReason(models.TextChoices):
    REQUESTER = "waiting_requester", "Ожидание инициатора"
    EXTERNAL = "waiting_external", "Внешняя зависимость"
    MATERIAL = "waiting_material", "Ожидание материалов"
    APPROVAL = "waiting_approval", "Ожидание согласования"
    OTHER = "waiting_other", "Другое"


class AcceptancePolicy(models.TextChoices):
    NONE = "none", "Без приёмки"
    AUTHOR = "author", "Автор"
    RESPONSIBLE = "responsible", "Ответственный"


class CompletionPolicy(models.TextChoices):
    MANUAL = "manual", "Ручное завершение"
    ALL_CHILDREN_COMPLETED = "all_children_completed", "Все подзадачи завершены"


class SourceType(models.TextChoices):
    MANUAL = "manual", "Вручную"
    REQUEST = "request", "Заявка"
    PROJECT = "project", "Проект"
    INCIDENT = "incident", "Инцидент"
    CHECKLIST = "checklist", "Чек-лист"
    AUTOMATION = "automation", "Автоматизация"
    API = "api", "API"
    TEMPLATE = "template", "Шаблон"
    RECURRENCE = "recurrence", "Повторение"


class TaskNumberSequence(models.Model):
    key = models.CharField(max_length=32, primary_key=True, default="task")
    value = models.PositiveBigIntegerField(default=0)


class Task(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    number = models.CharField(max_length=32, unique=True, editable=False)
    title = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    author = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="authored_work_tasks")
    responsible_target = models.ForeignKey("employees.AssignmentTarget", on_delete=models.PROTECT, null=True, blank=True, related_name="responsible_work_tasks")
    responsible_employee = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, null=True, blank=True, related_name="responsible_work_tasks")
    executor_target = models.ForeignKey("employees.AssignmentTarget", on_delete=models.PROTECT, null=True, blank=True, related_name="executor_work_tasks")
    executor_employee = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, null=True, blank=True, related_name="executed_work_tasks")
    status = models.CharField(max_length=20, choices=TaskStatus.choices, default=TaskStatus.DRAFT, db_index=True)
    priority = models.CharField(max_length=20, choices=TaskPriority.choices, default=TaskPriority.NORMAL, db_index=True)
    planned_start_at = models.DateTimeField(null=True, blank=True)
    initial_due_at = models.DateTimeField(null=True, blank=True, editable=False)
    due_at = models.DateTimeField(null=True, blank=True, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    waiting_reason = models.CharField(max_length=32, choices=WaitingReason.choices, blank=True)
    waiting_comment = models.TextField(blank=True)
    expected_resume_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)
    completion_comment = models.TextField(blank=True)
    parent = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="children")
    org_unit = models.ForeignKey("organizations.OrgUnit", on_delete=models.PROTECT, null=True, blank=True, related_name="work_tasks")
    legal_entity = models.ForeignKey("organizations.LegalEntity", on_delete=models.PROTECT, null=True, blank=True, related_name="work_tasks")
    location = models.ForeignKey("organizations.Location", on_delete=models.PROTECT, null=True, blank=True, related_name="work_tasks")
    completion_policy = models.CharField(max_length=32, choices=CompletionPolicy.choices, default=CompletionPolicy.MANUAL)
    acceptance_policy = models.CharField(max_length=24, choices=AcceptancePolicy.choices, default=AcceptancePolicy.NONE)
    source_type = models.CharField(max_length=24, choices=SourceType.choices, default=SourceType.MANUAL)
    source_id = models.CharField(max_length=64, blank=True)
    source_template = models.ForeignKey("TaskTemplate", on_delete=models.PROTECT, null=True, blank=True, related_name="created_tasks")
    recurrence_rule = models.ForeignKey("TaskRecurrenceRule", on_delete=models.PROTECT, null=True, blank=True, related_name="generated_tasks")
    version = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_work_tasks")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="updated_work_tasks")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["author"]), models.Index(fields=["responsible_employee"]),
            models.Index(fields=["executor_employee"]), models.Index(fields=["org_unit"]),
            models.Index(fields=["legal_entity"]), models.Index(fields=["location"]),
            models.Index(fields=["parent"]), models.Index(fields=["status", "due_at"]),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(planned_start_at__isnull=True) | models.Q(due_at__isnull=True) | models.Q(planned_start_at__lte=models.F("due_at")), name="work_task_planned_before_due"),
            models.CheckConstraint(condition=~models.Q(id=models.F("parent_id")), name="work_task_parent_not_self"),
            models.CheckConstraint(condition=~models.Q(status=TaskStatus.COMPLETED) | models.Q(completed_at__isnull=False), name="work_task_completed_has_timestamp"),
            models.CheckConstraint(condition=~models.Q(status=TaskStatus.CANCELLED) | models.Q(cancelled_at__isnull=False), name="work_task_cancelled_has_timestamp"),
        ]

    @property
    def is_overdue(self):
        return bool(self.due_at and self.due_at < timezone.now() and self.status not in {TaskStatus.COMPLETED, TaskStatus.CANCELLED})

    @property
    def completed_late(self):
        return bool(self.completed_at and self.due_at and self.completed_at > self.due_at)

    def delete(self, *args, **kwargs):
        raise TypeError("Production Task cannot be hard deleted")

    def save(self, *args, **kwargs):
        if self.pk:
            original = Task.objects.filter(pk=self.pk).values_list("number", flat=True).first()
            if original is not None and self.number != original:
                raise TypeError("Task number is immutable")
        return super().save(*args, **kwargs)


class TaskStatusHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.PROTECT, related_name="status_history")
    from_status = models.CharField(max_length=20, choices=TaskStatus.choices, blank=True)
    to_status = models.CharField(max_length=20, choices=TaskStatus.choices)
    actor = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="task_status_changes")
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)


class TaskWaitingPeriod(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.PROTECT, related_name="waiting_periods")
    reason = models.CharField(max_length=32, choices=WaitingReason.choices)
    comment = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    expected_resume_at = models.DateTimeField(null=True, blank=True)
    started_by = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="started_waiting_periods")
    ended_by = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, null=True, blank=True, related_name="ended_waiting_periods")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["task"], condition=models.Q(ended_at__isnull=True), name="one_active_waiting_period_per_task")]


class TaskDeadlineHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.PROTECT, related_name="deadline_history")
    old_due_at = models.DateTimeField(null=True, blank=True)
    new_due_at = models.DateTimeField(null=True, blank=True)
    changed_by = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="task_deadline_changes")
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class TaskAssignmentHistory(models.Model):
    class Type(models.TextChoices):
        RESPONSIBLE = "responsible", "Ответственный"
        EXECUTOR = "executor", "Исполнитель"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.PROTECT, related_name="assignment_history")
    assignment_type = models.CharField(max_length=20, choices=Type.choices)
    old_target = models.ForeignKey("employees.AssignmentTarget", on_delete=models.PROTECT, null=True, blank=True, related_name="old_task_assignments")
    old_employee = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, null=True, blank=True, related_name="old_task_assignments")
    new_target = models.ForeignKey("employees.AssignmentTarget", on_delete=models.PROTECT, related_name="new_task_assignments")
    new_employee = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="new_task_assignments")
    changed_by = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="task_assignment_changes")
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class TaskReviewHistory(models.Model):
    class Action(models.TextChoices):
        SUBMITTED = "submitted", "Отправлено"
        ACCEPTED = "accepted", "Принято"
        REJECTED = "rejected", "Отклонено"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.PROTECT, related_name="review_history")
    action = models.CharField(max_length=20, choices=Action.choices)
    actor = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="task_reviews")
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class TaskComment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.PROTECT, related_name="production_comments")
    author = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="task_comments")
    body = models.TextField()
    is_internal = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, null=True, blank=True, related_name="deleted_task_comments")

    class Meta:
        ordering = ("created_at", "id")
        indexes = [models.Index(fields=["task", "created_at"])]


class TaskCommentRevision(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    comment = models.ForeignKey(TaskComment, on_delete=models.PROTECT, related_name="revisions")
    body = models.TextField()
    edited_by = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="task_comment_revisions")
    created_at = models.DateTimeField(auto_now_add=True)


class TaskCommentMention(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    comment = models.ForeignKey(TaskComment, on_delete=models.PROTECT, related_name="mention_records")
    employee = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="task_comment_mentions")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["comment", "employee"], name="unique_task_comment_mention")]


def task_attachment_path(instance, filename):
    return f"tasks/{instance.task_id}/{instance.pk}/file"


class TaskAttachment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.PROTECT, related_name="production_attachments")
    file = models.FileField(upload_to=task_attachment_path, max_length=500)
    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=120)
    size = models.PositiveBigIntegerField()
    checksum = models.CharField(max_length=64, db_index=True)
    uploaded_by = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="uploaded_task_attachments")
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, null=True, blank=True, related_name="deleted_task_attachments")

    class Meta:
        ordering = ("created_at", "id")
        indexes = [models.Index(fields=["task", "created_at"])]


class TaskWatcher(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.PROTECT, related_name="watcher_records")
    employee = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="watched_tasks")
    added_by = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="added_task_watchers")
    created_at = models.DateTimeField(auto_now_add=True)
    removed_at = models.DateTimeField(null=True, blank=True)
    removed_by = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, null=True, blank=True, related_name="removed_task_watchers")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["task", "employee"], condition=models.Q(removed_at__isnull=True), name="unique_active_task_watcher")]
        indexes = [models.Index(fields=["task", "employee", "removed_at"])]


class ChecklistTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="created_checklist_templates")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class ChecklistTemplateItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(ChecklistTemplate, on_delete=models.PROTECT, related_name="items")
    text = models.CharField(max_length=500)
    position = models.PositiveIntegerField()
    required = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("position", "id")
        constraints = [models.UniqueConstraint(fields=["template", "position"], name="unique_template_item_position")]


class TaskChecklist(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.PROTECT, related_name="production_checklists")
    name = models.CharField(max_length=200)
    source_template = models.ForeignKey(ChecklistTemplate, on_delete=models.PROTECT, null=True, blank=True, related_name="task_instances")
    created_by = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="created_task_checklists")
    created_at = models.DateTimeField(auto_now_add=True)
    removed_at = models.DateTimeField(null=True, blank=True)
    removed_by = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, null=True, blank=True, related_name="removed_task_checklists")

    class Meta:
        ordering = ("created_at", "id")


class TaskChecklistItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    checklist = models.ForeignKey(TaskChecklist, on_delete=models.PROTECT, related_name="items")
    text = models.CharField(max_length=500)
    position = models.PositiveIntegerField()
    required = models.BooleanField(default=False)
    is_completed = models.BooleanField(default=False, db_index=True)
    completed_by = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, null=True, blank=True, related_name="completed_task_checklist_items")
    completed_at = models.DateTimeField(null=True, blank=True)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("position", "id")
        constraints = [
            models.UniqueConstraint(fields=["checklist", "position"], name="unique_task_checklist_item_position"),
            models.CheckConstraint(condition=models.Q(is_completed=False, completed_by__isnull=True, completed_at__isnull=True) | models.Q(is_completed=True, completed_by__isnull=False, completed_at__isnull=False), name="checklist_completion_consistent"),
        ]


class DeadlineRule(models.TextChoices):
    NONE = "none", "Без срока"
    AFTER_CREATION = "after_creation", "После создания"
    AFTER_PLANNED_START = "after_planned_start", "После планового начала"


class TaskTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    task_title = models.CharField(max_length=240)
    task_description = models.TextField(blank=True)
    default_priority = models.CharField(max_length=20, choices=TaskPriority.choices, default=TaskPriority.NORMAL)
    responsible_target = models.ForeignKey("employees.AssignmentTarget", on_delete=models.PROTECT, null=True, blank=True, related_name="responsible_task_templates")
    executor_target = models.ForeignKey("employees.AssignmentTarget", on_delete=models.PROTECT, null=True, blank=True, related_name="executor_task_templates")
    acceptance_policy = models.CharField(max_length=24, choices=AcceptancePolicy.choices, default=AcceptancePolicy.NONE)
    completion_policy = models.CharField(max_length=32, choices=CompletionPolicy.choices, default=CompletionPolicy.MANUAL)
    planned_start_offset = models.DurationField(null=True, blank=True)
    deadline_rule = models.CharField(max_length=32, choices=DeadlineRule.choices, default=DeadlineRule.NONE)
    deadline_offset = models.DurationField(null=True, blank=True)
    org_unit = models.ForeignKey("organizations.OrgUnit", on_delete=models.PROTECT, null=True, blank=True, related_name="task_templates")
    legal_entity = models.ForeignKey("organizations.LegalEntity", on_delete=models.PROTECT, null=True, blank=True, related_name="task_templates")
    location = models.ForeignKey("organizations.Location", on_delete=models.PROTECT, null=True, blank=True, related_name="task_templates")
    checklist_templates = models.ManyToManyField(ChecklistTemplate, through="TaskTemplateChecklist", related_name="task_templates")
    is_active = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="created_task_templates")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class TaskTemplateChecklist(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task_template = models.ForeignKey(TaskTemplate, on_delete=models.PROTECT, related_name="checklist_links")
    checklist_template = models.ForeignKey(ChecklistTemplate, on_delete=models.PROTECT, related_name="task_template_links")
    position = models.PositiveIntegerField()

    class Meta:
        ordering = ("position", "id")
        constraints = [
            models.UniqueConstraint(fields=["task_template", "checklist_template"], name="unique_task_template_checklist"),
            models.UniqueConstraint(fields=["task_template", "position"], name="unique_task_template_checklist_position"),
        ]


class TaskRecurrenceRule(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    task_template = models.ForeignKey(TaskTemplate, on_delete=models.PROTECT, related_name="recurrence_rules")
    rrule = models.CharField(max_length=500)
    timezone = models.CharField(max_length=64)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    next_occurrence_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_generated_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    created_by = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="created_task_recurrences")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["is_active", "next_occurrence_at"])]

    def __str__(self):
        return self.name


class TaskOccurrence(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает"
        GENERATED = "generated", "Создано"
        FAILED = "failed", "Ошибка"
        SKIPPED = "skipped", "Пропущено"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recurrence_rule = models.ForeignKey(TaskRecurrenceRule, on_delete=models.PROTECT, related_name="occurrences")
    occurrence_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    task = models.OneToOneField(Task, on_delete=models.PROTECT, null=True, blank=True, related_name="source_occurrence")
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    skipped_by = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, null=True, blank=True, related_name="skipped_task_occurrences")
    skip_reason = models.TextField(blank=True)

    class Meta:
        ordering = ("-occurrence_at", "-id")
        constraints = [models.UniqueConstraint(fields=["recurrence_rule", "occurrence_at"], name="unique_task_recurrence_occurrence")]
        indexes = [models.Index(fields=["status", "occurrence_at"])]


class TaskSavedView(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="task_saved_views")
    name = models.CharField(max_length=150)
    filters = models.JSONField(default=dict)
    ordering = models.CharField(max_length=32, default="-created_at")
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name", "id")
        constraints = [
            models.UniqueConstraint(fields=["owner", "name"], condition=models.Q(is_active=True), name="unique_active_saved_view_name"),
            models.UniqueConstraint(fields=["owner"], condition=models.Q(is_active=True, is_default=True), name="one_default_task_saved_view"),
        ]
