import uuid

from django.conf import settings
from django.db import models


class ProjectStatus(models.TextChoices):
    DRAFT = "draft", "Черновик"
    ACTIVE = "active", "Активен"
    ON_HOLD = "on_hold", "Приостановлен"
    COMPLETED = "completed", "Завершён"
    CANCELLED = "cancelled", "Отменён"


class ProjectNumberSequence(models.Model):
    key = models.CharField(max_length=32, primary_key=True, default="project")
    value = models.PositiveBigIntegerField(default=0)


class Project(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    number = models.CharField(max_length=32, unique=True, editable=False)
    name = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    goal = models.TextField(blank=True)
    expected_result = models.TextField(blank=True)
    manager = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, null=True, blank=True, related_name="managed_projects")
    customer = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, null=True, blank=True, related_name="customer_projects")
    org_unit = models.ForeignKey("organizations.OrgUnit", on_delete=models.PROTECT, null=True, blank=True, related_name="projects")
    location = models.ForeignKey("organizations.Location", on_delete=models.PROTECT, null=True, blank=True, related_name="projects")
    planned_start_at = models.DateTimeField(null=True, blank=True)
    planned_end_at = models.DateTimeField(null=True, blank=True)
    actual_start_at = models.DateTimeField(null=True, blank=True)
    actual_end_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=ProjectStatus.choices, default=ProjectStatus.DRAFT, db_index=True)
    is_archived = models.BooleanField(default=False, db_index=True)
    version = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_projects")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="updated_projects")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["org_unit", "status"]), models.Index(fields=["location", "status"]), models.Index(fields=["manager"])]
        constraints = [models.CheckConstraint(condition=models.Q(planned_start_at__isnull=True) | models.Q(planned_end_at__isnull=True) | models.Q(planned_start_at__lte=models.F("planned_end_at")), name="project_planned_dates_order")]

    def save(self, *args, **kwargs):
        if self.pk and Project.objects.filter(pk=self.pk).exclude(number=self.number).exists():
            raise ValueError("Project number is immutable")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise TypeError("Project cannot be hard deleted")


class ProjectMember(models.Model):
    class Role(models.TextChoices):
        MANAGER = "manager", "Руководитель"
        MEMBER = "member", "Участник"
        OBSERVER = "observer", "Наблюдатель"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="members")
    employee = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="project_memberships")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="added_project_members")
    removed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="removed_project_members")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["project", "employee"], condition=models.Q(left_at__isnull=True), name="project_one_active_member")]
        indexes = [models.Index(fields=["employee", "left_at"])]


class ProjectStage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="stages")
    name = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    position = models.PositiveIntegerField(default=1)
    planned_start_at = models.DateTimeField(null=True, blank=True)
    planned_end_at = models.DateTimeField(null=True, blank=True)
    responsible = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, null=True, blank=True, related_name="responsible_project_stages")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("position", "id")
        constraints = [models.CheckConstraint(condition=models.Q(planned_start_at__isnull=True) | models.Q(planned_end_at__isnull=True) | models.Q(planned_start_at__lte=models.F("planned_end_at")), name="project_stage_dates_order")]


class ProjectMilestone(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="milestones")
    stage = models.ForeignKey(ProjectStage, on_delete=models.PROTECT, null=True, blank=True, related_name="milestones")
    name = models.CharField(max_length=240)
    due_at = models.DateTimeField(null=True, blank=True)
    criterion = models.TextField(blank=True)
    required = models.BooleanField(default=False)
    responsible = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, null=True, blank=True, related_name="responsible_project_milestones")
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, null=True, blank=True, related_name="confirmed_project_milestones")
    confirmation_comment = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="created_project_milestones")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ProjectMilestoneHistory(models.Model):
    class Action(models.TextChoices):
        CONFIRM = "confirm", "Подтверждение"
        REOPEN = "reopen", "Повторное открытие"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    milestone = models.ForeignKey(ProjectMilestone, on_delete=models.PROTECT, related_name="history")
    action = models.CharField(max_length=20, choices=Action.choices)
    actor = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="project_milestone_changes")
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ProjectMilestoneDueNotice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    milestone = models.ForeignKey(ProjectMilestone, on_delete=models.PROTECT, related_name="due_notices")
    due_at = models.DateTimeField()
    recipient = models.ForeignKey("employees.Employee", on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["milestone", "due_at", "recipient"], name="project_due_notice_once")]


class ProjectCreateRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    key = models.UUIDField()
    operation = models.CharField(max_length=24)
    payload_hash = models.CharField(max_length=64)
    project = models.ForeignKey(Project, on_delete=models.PROTECT, null=True, blank=True)
    task = models.ForeignKey("work_tasks.Task", on_delete=models.PROTECT, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["actor", "key", "operation"], name="project_create_request_once")]


class ProjectTaskLink(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.OneToOneField("work_tasks.Task", on_delete=models.PROTECT, related_name="project_link")
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="task_links")
    stage = models.ForeignKey(ProjectStage, on_delete=models.PROTECT, null=True, blank=True, related_name="task_links")
    version = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True, db_index=True)
    unlinked_at = models.DateTimeField(null=True, blank=True)
    linked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="linked_project_tasks")
    linked_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["project", "stage"])]


class ProjectTaskLinkHistory(models.Model):
    class Action(models.TextChoices):
        LINK = "link", "Привязка"
        UNLINK = "unlink", "Отвязка"
        STAGE = "stage", "Перенос этапа"
        PROJECT = "project", "Перенос проекта"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey("work_tasks.Task", on_delete=models.PROTECT, related_name="project_link_history")
    action = models.CharField(max_length=20, choices=Action.choices)
    old_project = models.ForeignKey(Project, on_delete=models.PROTECT, null=True, blank=True, related_name="old_task_links")
    new_project = models.ForeignKey(Project, on_delete=models.PROTECT, null=True, blank=True, related_name="new_task_links")
    old_stage = models.ForeignKey(ProjectStage, on_delete=models.PROTECT, null=True, blank=True, related_name="old_task_links")
    new_stage = models.ForeignKey(ProjectStage, on_delete=models.PROTECT, null=True, blank=True, related_name="new_task_links")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="project_task_link_changes")
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ProjectComment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="comments")
    author = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="project_comments")
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, null=True, blank=True, related_name="deleted_project_comments")

    class Meta:
        ordering = ("created_at", "id")


class ProjectCommentMention(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    comment = models.ForeignKey(ProjectComment, on_delete=models.PROTECT, related_name="mentions")
    employee = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="project_comment_mentions")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["comment", "employee"], name="project_comment_mention_unique")]


def project_attachment_path(instance, filename):
    return f"projects/{instance.project_id}/{instance.pk}/file"


class ProjectAttachment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="attachments")
    file = models.FileField(upload_to=project_attachment_path, max_length=500)
    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=120)
    size = models.PositiveBigIntegerField()
    checksum = models.CharField(max_length=64, db_index=True)
    uploaded_by = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="project_attachments")
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, null=True, blank=True, related_name="deleted_project_attachments")

    class Meta:
        ordering = ("created_at", "id")
