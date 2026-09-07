from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField, RangeOperators
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
import uuid


class Position(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=64, blank=True, null=True, unique=True)
    org_unit = models.ForeignKey("organizations.OrgUnit", on_delete=models.PROTECT, null=True, blank=True, related_name="positions")
    legal_entity = models.ForeignKey("organizations.LegalEntity", on_delete=models.PROTECT, null=True, blank=True, related_name="positions")
    allows_multiple_occupants = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Employee(models.Model):
    class AccountAccessState(models.TextChoices):
        NORMAL = "normal", "Обычный доступ"
        SUSPENDED = "suspended", "Доступ приостановлен"
        BLOCKED = "blocked", "Доступ заблокирован"
        REACTIVATION_REQUIRED = "reactivation_required", "Требуется реактивация"
    class Status(models.TextChoices):
        ACTIVE = "active", "Работает"
        VACATION = "vacation", "Отпуск"
        SICK = "sick", "Больничный"
        ARCHIVED = "archived", "Архив"
        ON_LEAVE = "on_leave", "В отпуске"
        SUSPENDED = "suspended", "Отстранён"
        DISMISSED = "dismissed", "Уволен"
        INACTIVE = "inactive", "Неактивен"
        ONBOARDING = "onboarding", "Оформление"
        TERMINATED = "terminated", "Уволен"
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="employee")
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    middle_name = models.CharField(max_length=150, blank=True)
    company = models.ForeignKey("organizations.Company", on_delete=models.PROTECT, related_name="employees", null=True, blank=True)
    department = models.ForeignKey("organizations.Department", on_delete=models.SET_NULL, null=True, blank=True, related_name="employees")
    position_ref = models.ForeignKey(Position, on_delete=models.SET_NULL, null=True, blank=True, related_name="employees")
    org_unit = models.ForeignKey("organizations.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="employees")
    legal_entity = models.ForeignKey("organizations.LegalEntity", on_delete=models.PROTECT, null=True, blank=True, related_name="employees")
    primary_location = models.ForeignKey("organizations.Location", on_delete=models.SET_NULL, null=True, blank=True, related_name="primary_employees")
    manager = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="reports")
    employee_number = models.CharField(max_length=30, unique=True, null=True, blank=True)
    avatar = models.FileField(upload_to="employees/avatars/%Y/%m/", null=True, blank=True)
    work_email = models.EmailField(blank=True)
    work_phone = models.CharField(max_length=40, blank=True)
    position = models.CharField(max_length=150, blank=True)
    hire_date = models.DateField(null=True, blank=True)
    dismissed_at = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    account_access_state = models.CharField(max_length=24, choices=AccountAccessState.choices, default=AccountAccessState.NORMAL, db_index=True)
    work_schedule = models.CharField(max_length=100, default="5/2, 09:00–18:00")
    skills = models.JSONField(default=list, blank=True)
    is_demo = models.BooleanField(default=False)
    facilities = models.ManyToManyField("organizations.Facility", through="EmployeeFacility", related_name="employees")
    @property
    def display_name(self):
        parts = (self.last_name, self.first_name, self.middle_name)
        value = " ".join(part for part in parts if part).strip()
        return value or (self.user.get_full_name() if self.user else "")
    def __str__(self): return f"{self.employee_number} — {self.position}"
    @property
    def termination_date(self):
        return self.dismissed_at

    def save(self, *args, **kwargs):
        adding = self._state.adding
        if adding and not self.employee_number:
            from .services import EmployeeNumberService
            self.employee_number = EmployeeNumberService.allocate()
        elif not adding:
            previous = type(self).objects.filter(pk=self.pk).values_list("employee_number", flat=True).first()
            if previous and self.employee_number != previous:
                raise ValidationError({"employee_number": "Employee number is immutable."})
        self.updated_at = timezone.now()
        return super().save(*args, **kwargs)
    class Meta:
        ordering = ["last_name", "first_name"]
        indexes = [models.Index(fields=["position_ref"]), models.Index(fields=["org_unit"]), models.Index(fields=["legal_entity"]), models.Index(fields=["manager"])]


class EmployeeNumberSequence(models.Model):
    key = models.CharField(max_length=32, unique=True, default="employee")
    next_value = models.PositiveBigIntegerField(default=1)


class EmployeeAssignment(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Активно"
        ENDED = "ended", "Завершено"
        CANCELLED = "cancelled", "Отменено"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="organizational_assignments")
    position = models.ForeignKey(Position, on_delete=models.PROTECT, null=True, blank=True, related_name="employee_assignments")
    org_unit = models.ForeignKey("organizations.OrgUnit", on_delete=models.PROTECT, null=True, blank=True, related_name="employee_assignments")
    legal_entity = models.ForeignKey("organizations.LegalEntity", on_delete=models.PROTECT, null=True, blank=True, related_name="employee_assignments")
    location = models.ForeignKey("organizations.Location", on_delete=models.PROTECT, null=True, blank=True, related_name="employee_assignments")
    is_primary = models.BooleanField(default=False)
    valid_from = models.DateTimeField(default=timezone.now)
    valid_to = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-valid_from", "created_at"]
        indexes = [
            models.Index(fields=["employee", "status"]),
            models.Index(fields=["org_unit", "status"]),
            models.Index(fields=["legal_entity", "status"]),
            models.Index(fields=["location", "status"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["employee"], condition=models.Q(is_primary=True, status="active"), name="one_active_primary_employee_assignment"),
            models.CheckConstraint(condition=models.Q(valid_to__isnull=True) | models.Q(valid_to__gte=models.F("valid_from")), name="employee_assignment_valid_period"),
        ]


class EmployeeManagerAssignment(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Активно"
        ENDED = "ended", "Завершено"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="manager_assignments")
    manager = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="report_assignments")
    valid_from = models.DateTimeField(default=timezone.now)
    valid_to = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-valid_from", "created_at"]
        indexes = [models.Index(fields=["employee", "status"]), models.Index(fields=["manager", "status"])]
        constraints = [
            models.UniqueConstraint(fields=["employee"], condition=models.Q(status="active"), name="one_active_manager_assignment"),
            models.CheckConstraint(condition=~models.Q(employee=models.F("manager")), name="employee_manager_not_self"),
            models.CheckConstraint(condition=models.Q(valid_to__isnull=True) | models.Q(valid_to__gte=models.F("valid_from")), name="employee_manager_valid_period"),
        ]


class FunctionalGroup(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=64, blank=True, null=True, unique=True)
    org_unit = models.ForeignKey("organizations.OrgUnit", on_delete=models.PROTECT, null=True, blank=True, related_name="functional_groups")
    legal_entity = models.ForeignKey("organizations.LegalEntity", on_delete=models.PROTECT, null=True, blank=True, related_name="functional_groups")
    location = models.ForeignKey("organizations.Location", on_delete=models.PROTECT, null=True, blank=True, related_name="functional_groups")
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class FunctionalGroupMembership(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(FunctionalGroup, on_delete=models.PROTECT, related_name="memberships")
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="functional_group_memberships")
    role = models.CharField(max_length=100, blank=True)
    active_from = models.DateTimeField(null=True, blank=True)
    active_until = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["employee"]), models.Index(fields=["group"])]
        constraints = [models.UniqueConstraint(fields=["group", "employee"], condition=models.Q(is_active=True), name="unique_active_group_membership")]


class TeamNumberSequence(models.Model):
    key = models.CharField(max_length=32, unique=True, default="team")
    next_value = models.PositiveBigIntegerField(default=1)


class Team(models.Model):
    class Type(models.TextChoices):
        FUNCTIONAL = "functional", "Функциональная"
        CROSS_FUNCTIONAL = "cross_functional", "Кросс-функциональная"
        PROJECT = "project", "Проектная"
        SERVICE = "service", "Сервисная"
        COMMITTEE = "committee", "Комитет"
        TEMPORARY = "temporary", "Временная"
        OTHER = "other", "Другая"

    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        ACTIVE = "active", "Активна"
        SUSPENDED = "suspended", "Приостановлена"
        CLOSED = "closed", "Закрыта"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=32, unique=True, editable=False)
    name = models.CharField(max_length=150)
    short_name = models.CharField(max_length=80, blank=True)
    description = models.TextField(blank=True)
    team_type = models.CharField(max_length=32, choices=Type.choices, default=Type.FUNCTIONAL, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    legal_entity = models.ForeignKey("organizations.LegalEntity", on_delete=models.PROTECT, null=True, blank=True, related_name="teams")
    org_unit = models.ForeignKey("organizations.OrgUnit", on_delete=models.PROTECT, null=True, blank=True, related_name="teams")
    location = models.ForeignKey("organizations.Location", on_delete=models.PROTECT, null=True, blank=True, related_name="teams")
    parent_team = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="child_teams")
    owner_employee = models.ForeignKey(Employee, on_delete=models.PROTECT, null=True, blank=True, related_name="owned_teams")
    lead_employee = models.ForeignKey(Employee, on_delete=models.PROTECT, null=True, blank=True, related_name="led_teams")
    valid_from = models.DateTimeField(default=timezone.now)
    valid_to = models.DateTimeField(null=True, blank=True)
    is_assignable = models.BooleanField(default=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="teams_created")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="teams_updated")
    version = models.PositiveIntegerField(default=1)

    def save(self,*args,**kwargs):
        if not self._state.adding:
            previous=type(self).objects.filter(pk=self.pk).values_list("code",flat=True).first()
            if previous and self.code!=previous: raise ValidationError({"code":"Team code is immutable."})
        return super().save(*args,**kwargs)

    class Meta:
        indexes = [models.Index(fields=["parent_team"]), models.Index(fields=["legal_entity", "status"]), models.Index(fields=["org_unit", "status"]), models.Index(fields=["location", "status"]), models.Index(fields=["owner_employee"]), models.Index(fields=["lead_employee"])]
        constraints = [
            models.CheckConstraint(condition=~models.Q(id=models.F("parent_team_id")), name="team_parent_not_self"),
            models.CheckConstraint(condition=models.Q(valid_to__isnull=True) | models.Q(valid_to__gte=models.F("valid_from")), name="team_valid_period"),
        ]


class TeamMembership(models.Model):
    class Role(models.TextChoices):
        LEAD = "lead", "Руководитель"
        DEPUTY = "deputy", "Заместитель"
        MEMBER = "member", "Участник"
        COORDINATOR = "coordinator", "Координатор"
        OBSERVER = "observer", "Наблюдатель"

    class Type(models.TextChoices):
        PERMANENT = "permanent", "Постоянное"
        TEMPORARY = "temporary", "Временное"
        OBSERVER = "observer", "Наблюдатель"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="memberships")
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="team_memberships")
    role = models.CharField(max_length=24, choices=Role.choices, default=Role.MEMBER)
    membership_type = models.CharField(max_length=24, choices=Type.choices, default=Type.PERMANENT)
    valid_from = models.DateTimeField(default=timezone.now)
    valid_to = models.DateTimeField(null=True, blank=True)
    allocation_percent = models.PositiveSmallIntegerField(null=True, blank=True)
    is_primary_in_team = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="team_memberships_created")
    ended_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="team_memberships_ended")
    end_reason = models.CharField(max_length=240, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["-valid_from", "created_at"]
        indexes = [models.Index(fields=["team", "employee"]), models.Index(fields=["team", "valid_from", "valid_to"]), models.Index(fields=["employee", "valid_from", "valid_to"])]
        constraints = [
            models.CheckConstraint(condition=models.Q(valid_to__isnull=True) | models.Q(valid_to__gte=models.F("valid_from")), name="team_membership_valid_period"),
            models.CheckConstraint(condition=models.Q(allocation_percent__isnull=True) | models.Q(allocation_percent__gte=1, allocation_percent__lte=100), name="team_membership_allocation_range"),
            models.UniqueConstraint(fields=["team", "employee"], condition=models.Q(valid_to__isnull=True), name="one_open_team_membership"),
            models.UniqueConstraint(fields=["team"], condition=models.Q(valid_to__isnull=True, role="lead", is_primary_in_team=True), name="one_primary_team_lead"),
            ExclusionConstraint(
                name="team_membership_no_period_overlap",
                expressions=[
                    ("team", RangeOperators.EQUAL),
                    ("employee", RangeOperators.EQUAL),
                    (
                        models.Func(
                            models.F("valid_from"),
                            models.F("valid_to"),
                            models.Value("[)"),
                            function="TSTZRANGE",
                            output_field=DateTimeRangeField(),
                        ),
                        RangeOperators.OVERLAPS,
                    ),
                ],
            ),
        ]


class AssignmentTarget(models.Model):
    class Type(models.TextChoices):
        EMPLOYEE = "employee", "Сотрудник"
        POSITION = "position", "Должность"
        ORG_UNIT = "org_unit", "Подразделение"
        FUNCTIONAL_GROUP = "functional_group", "Функциональная группа"
        TEAM = "team", "Команда"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    target_type = models.CharField(max_length=32, choices=Type.choices)
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, null=True, blank=True, related_name="assignment_targets")
    position = models.ForeignKey(Position, on_delete=models.PROTECT, null=True, blank=True, related_name="assignment_targets")
    org_unit = models.ForeignKey("organizations.OrgUnit", on_delete=models.PROTECT, null=True, blank=True, related_name="assignment_targets")
    functional_group = models.ForeignKey(FunctionalGroup, on_delete=models.PROTECT, null=True, blank=True, related_name="assignment_targets")
    team = models.ForeignKey(Team, on_delete=models.PROTECT, null=True, blank=True, related_name="assignment_targets")
    strategy = models.CharField(max_length=32, blank=True)
    team_role = models.CharField(max_length=24, blank=True)
    explicit_employee = models.ForeignKey(Employee, on_delete=models.PROTECT, null=True, blank=True, related_name="explicit_assignment_targets")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=(
            models.Q(target_type="employee", employee__isnull=False, position__isnull=True, org_unit__isnull=True, functional_group__isnull=True, team__isnull=True, explicit_employee__isnull=True)
            | models.Q(target_type="position", employee__isnull=True, position__isnull=False, org_unit__isnull=True, functional_group__isnull=True, team__isnull=True, explicit_employee__isnull=True)
            | models.Q(target_type="org_unit", employee__isnull=True, position__isnull=True, org_unit__isnull=False, functional_group__isnull=True, team__isnull=True, explicit_employee__isnull=True)
            | models.Q(target_type="functional_group", employee__isnull=True, position__isnull=True, org_unit__isnull=True, functional_group__isnull=False, team__isnull=True, explicit_employee__isnull=True)
            | models.Q(target_type="team", employee__isnull=True, position__isnull=True, org_unit__isnull=True, functional_group__isnull=True, team__isnull=False)
        ), name="assignment_target_exactly_one_reference")]

class EmployeeFacility(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    facility = models.ForeignKey("organizations.Facility", on_delete=models.CASCADE)
    is_primary = models.BooleanField(default=False)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["employee", "facility"], name="unique_employee_facility")]


class EmployeeInvitation(models.Model):
    class Status(models.TextChoices):
        CREATED = "created", "Создано"
        SENT = "sent", "Отправлено"
        ACCEPTED = "accepted", "Принято"
        REVOKED = "revoked", "Отозвано"
        EXPIRED = "expired", "Истекло"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="invitations")
    token_hash = models.CharField(max_length=64, unique=True)
    token_prefix = models.CharField(max_length=12, blank=True, editable=False)
    delivery_address = models.EmailField(blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.CREATED, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="employee_invitations_created")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    accepted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="employee_invitations_accepted")
    revoke_reason = models.CharField(max_length=240, blank=True)
    version = models.PositiveIntegerField(default=1)

    def save(self, *args, **kwargs):
        if self.expires_at and self.created_at and self.expires_at <= timezone.now() and self.expires_at <= self.created_at:
            self.status = self.Status.EXPIRED
            update_fields = kwargs.get("update_fields")
            if update_fields is not None:
                kwargs["update_fields"] = set(update_fields) | {"status"}
        return super().save(*args, **kwargs)

    class Meta:
        indexes = [models.Index(fields=["employee", "expires_at"]), models.Index(fields=["status", "expires_at"])]
        constraints = [
            models.UniqueConstraint(fields=["employee"], condition=models.Q(used_at__isnull=True, revoked_at__isnull=True), name="one_open_employee_invitation"),
            models.CheckConstraint(condition=models.Q(expires_at__gt=models.F("created_at")) | models.Q(status="expired"), name="employee_invitation_expiry_after_creation"),
        ]


class RegistrationRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает проверки"
        APPROVED = "approved", "Одобрена"
        REJECTED = "rejected", "Отклонена"
        EXPIRED = "expired", "Истекла"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    full_name = models.CharField(max_length=300)
    email = models.EmailField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    matched_employee = models.ForeignKey(Employee, on_delete=models.PROTECT, null=True, blank=True, related_name="registration_requests")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="registration_requests_reviewed")
    rejection_code = models.CharField(max_length=80, blank=True)

    class Meta:
        indexes = [models.Index(fields=["email", "status", "created_at"])]
        constraints = [models.UniqueConstraint(models.functions.Lower("email"), condition=models.Q(status="pending"), name="one_pending_registration_email")]


class EmployeeProfile(models.Model):
    class Visibility(models.TextChoices):
        PRIVATE = "private", "Только я и HR"
        MANAGERS = "managers", "Руководители"
        TEAM = "team", "Команды"
        ORGANIZATION = "organization", "Организация"

    employee = models.OneToOneField(Employee, on_delete=models.CASCADE, related_name="profile")
    preferred_name = models.CharField(max_length=150, blank=True)
    bio = models.TextField(max_length=1000, blank=True)
    additional_email = models.EmailField(blank=True)
    additional_phone = models.CharField(max_length=40, blank=True)
    timezone = models.CharField(max_length=64, default="Asia/Novosibirsk")
    preferred_language = models.CharField(max_length=12, default="ru")
    bio_visibility = models.CharField(max_length=20, choices=Visibility.choices, default=Visibility.ORGANIZATION)
    additional_email_visibility = models.CharField(max_length=20, choices=Visibility.choices, default=Visibility.PRIVATE)
    additional_phone_visibility = models.CharField(max_length=20, choices=Visibility.choices, default=Visibility.PRIVATE)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class FirstLoginProgress(models.Model):
    employee = models.OneToOneField(Employee, on_delete=models.CASCADE, related_name="first_login_progress")
    profile_completed = models.BooleanField(default=False)
    timezone_completed = models.BooleanField(default=False)
    visibility_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class OnboardingTemplate(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        PUBLISHED = "published", "Опубликован"
        ARCHIVED = "archived", "Архив"

    class Scope(models.TextChoices):
        GLOBAL = "global", "Глобально"
        LEGAL_ENTITY = "legal_entity", "Юридическое лицо"
        ORG_UNIT = "org_unit", "Подразделение"
        LOCATION = "location", "Локация"
        POSITION = "position", "Должность"
        TEAM = "team", "Команда"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True)
    scope = models.CharField(max_length=24, choices=Scope.choices, default=Scope.GLOBAL, db_index=True)
    legal_entity = models.ForeignKey("organizations.LegalEntity", on_delete=models.PROTECT, null=True, blank=True, related_name="onboarding_templates")
    org_unit = models.ForeignKey("organizations.OrgUnit", on_delete=models.PROTECT, null=True, blank=True, related_name="onboarding_templates")
    location = models.ForeignKey("organizations.Location", on_delete=models.PROTECT, null=True, blank=True, related_name="onboarding_templates")
    position = models.ForeignKey(Position, on_delete=models.PROTECT, null=True, blank=True, related_name="onboarding_templates")
    team = models.ForeignKey(Team, on_delete=models.PROTECT, null=True, blank=True, related_name="onboarding_templates")
    published_version = models.ForeignKey("OnboardingTemplateVersion", on_delete=models.PROTECT, null=True, blank=True, related_name="published_for_templates")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="onboarding_templates_created")
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["status", "scope"]), models.Index(fields=["legal_entity", "org_unit", "position"])]


class OnboardingTemplateVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(OnboardingTemplate, on_delete=models.PROTECT, related_name="versions")
    number = models.PositiveIntegerField()
    name_snapshot = models.CharField(max_length=200)
    description_snapshot = models.TextField(blank=True)
    published_at = models.DateTimeField(default=timezone.now)
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="onboarding_versions_published")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["template", "number"], name="unique_onboarding_template_version")]
        ordering = ["template_id", "number"]


class OnboardingTemplateStep(models.Model):
    class Type(models.TextChoices):
        PROFILE = "profile", "Профиль"
        ACKNOWLEDGEMENT = "acknowledgement", "Ознакомление"
        MANUAL = "manual", "Ручной шаг"
        TASK = "task", "Задача"
        LINK = "link", "Ссылка"
        LEARNING_PLACEHOLDER = "learning_placeholder", "Обучение"

    class ResponsibleStrategy(models.TextChoices):
        SELF = "self", "Сам сотрудник"
        DIRECT_MANAGER = "direct_manager", "Прямой руководитель"
        POSITION = "position", "Должность"
        ORG_UNIT = "org_unit", "Подразделение"
        TEAM_LEAD = "team_lead", "Руководитель команды"
        TEAM_ROLE = "team_role", "Роль команды"
        EXPLICIT_EMPLOYEE = "explicit_employee", "Сотрудник"
        ASSIGNMENT_TARGET = "assignment_target", "Цель назначения"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version = models.ForeignKey(OnboardingTemplateVersion, on_delete=models.PROTECT, related_name="steps")
    key = models.SlugField(max_length=80)
    title = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    step_type = models.CharField(max_length=32, choices=Type.choices)
    position = models.PositiveIntegerField()
    required = models.BooleanField(default=True)
    due_offset = models.DurationField(null=True, blank=True)
    external_url = models.URLField(blank=True)
    task_template = models.ForeignKey("work_tasks.TaskTemplate", on_delete=models.PROTECT, null=True, blank=True, related_name="onboarding_steps")
    responsible_strategy = models.CharField(max_length=32, choices=ResponsibleStrategy.choices, default=ResponsibleStrategy.SELF)
    responsible_target = models.ForeignKey(AssignmentTarget, on_delete=models.PROTECT, null=True, blank=True, related_name="onboarding_steps")
    explicit_employee = models.ForeignKey(Employee, on_delete=models.PROTECT, null=True, blank=True, related_name="explicit_onboarding_steps")
    team_role = models.CharField(max_length=24, blank=True)
    dependencies = models.ManyToManyField("self", symmetrical=False, blank=True, related_name="dependents")

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(fields=["version", "key"], name="unique_onboarding_step_key"),
            models.UniqueConstraint(fields=["version", "position"], name="unique_onboarding_step_position"),
        ]


class OnboardingInstance(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает"
        ACTIVE = "active", "Активен"
        PAUSED = "paused", "Приостановлен"
        COMPLETED = "completed", "Завершён"
        CANCELLED = "cancelled", "Отменён"
        FAILED = "failed", "Ошибка"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="onboarding_instances")
    template_version = models.ForeignKey(OnboardingTemplateVersion, on_delete=models.PROTECT, related_name="instances")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    progress_percent = models.PositiveSmallIntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.CharField(max_length=500, blank=True)
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="onboarding_instances_assigned")
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["employee", "status"]), models.Index(fields=["status", "created_at"])]
        constraints = [
            models.UniqueConstraint(fields=["employee"], condition=models.Q(status__in=["pending", "active", "paused"]), name="one_active_onboarding_per_employee"),
            models.CheckConstraint(condition=models.Q(progress_percent__lte=100), name="onboarding_progress_lte_100"),
        ]


class OnboardingStepInstance(models.Model):
    class Status(models.TextChoices):
        BLOCKED = "blocked", "Заблокирован"
        PENDING = "pending", "Ожидает"
        IN_PROGRESS = "in_progress", "В работе"
        COMPLETED = "completed", "Завершён"
        SKIPPED = "skipped", "Пропущен"
        CANCELLED = "cancelled", "Отменён"
        FAILED = "failed", "Ошибка"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    onboarding = models.ForeignKey(OnboardingInstance, on_delete=models.PROTECT, related_name="steps")
    template_step = models.ForeignKey(OnboardingTemplateStep, on_delete=models.PROTECT, related_name="instances")
    title_snapshot = models.CharField(max_length=240)
    description_snapshot = models.TextField(blank=True)
    required = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    responsible_employee = models.ForeignKey(Employee, on_delete=models.PROTECT, null=True, blank=True, related_name="responsible_onboarding_steps")
    resolution_detail = models.JSONField(default=dict, blank=True)
    due_at = models.DateTimeField(null=True, blank=True, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(Employee, on_delete=models.PROTECT, null=True, blank=True, related_name="completed_onboarding_steps")
    skipped_at = models.DateTimeField(null=True, blank=True)
    skipped_by = models.ForeignKey(Employee, on_delete=models.PROTECT, null=True, blank=True, related_name="skipped_onboarding_steps")
    skip_reason = models.CharField(max_length=500, blank=True)
    task = models.OneToOneField("work_tasks.Task", on_delete=models.PROTECT, null=True, blank=True, related_name="onboarding_step")
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["onboarding", "status"]), models.Index(fields=["status", "due_at"])]
        constraints = [models.UniqueConstraint(fields=["onboarding", "template_step"], name="unique_onboarding_step_instance")]


class EmployeeDataChangeRequest(models.Model):
    class FieldType(models.TextChoices):
        LEGAL_NAME = "legal_name", "ФИО"
        WORK_EMAIL = "work_email", "Рабочая почта"
        WORK_PHONE = "work_phone", "Рабочий телефон"

    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Отправлен"
        APPROVED = "approved", "Одобрен"
        REJECTED = "rejected", "Отклонён"
        CANCELLED = "cancelled", "Отменён"
        APPLIED = "applied", "Применён"
        FAILED = "failed", "Ошибка"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="data_change_requests")
    field_type = models.CharField(max_length=24, choices=FieldType.choices)
    requested_value = models.JSONField(default=dict)
    current_value_snapshot = models.JSONField(default=dict)
    reason = models.CharField(max_length=500)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SUBMITTED, db_index=True)
    submitted_at = models.DateTimeField(default=timezone.now)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="employee_change_requests_reviewed")
    review_comment = models.CharField(max_length=500, blank=True)
    applied_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-submitted_at", "-created_at"]
        indexes = [models.Index(fields=["employee", "status", "submitted_at"])]
