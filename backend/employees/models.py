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
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="invitations")
    token_hash = models.CharField(max_length=64, unique=True)
    delivery_address = models.EmailField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="employee_invitations_created")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["employee", "expires_at"])]
        constraints = [models.UniqueConstraint(fields=["employee"], condition=models.Q(used_at__isnull=True, revoked_at__isnull=True), name="one_open_employee_invitation")]


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
