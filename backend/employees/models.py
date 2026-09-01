from django.conf import settings
from django.db import models
from django.utils import timezone
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
    class Meta:
        ordering = ["last_name", "first_name"]
        indexes = [models.Index(fields=["position_ref"]), models.Index(fields=["org_unit"]), models.Index(fields=["legal_entity"]), models.Index(fields=["manager"])]


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


class AssignmentTarget(models.Model):
    class Type(models.TextChoices):
        EMPLOYEE = "employee", "Сотрудник"
        POSITION = "position", "Должность"
        ORG_UNIT = "org_unit", "Подразделение"
        FUNCTIONAL_GROUP = "functional_group", "Функциональная группа"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    target_type = models.CharField(max_length=32, choices=Type.choices)
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, null=True, blank=True, related_name="assignment_targets")
    position = models.ForeignKey(Position, on_delete=models.PROTECT, null=True, blank=True, related_name="assignment_targets")
    org_unit = models.ForeignKey("organizations.OrgUnit", on_delete=models.PROTECT, null=True, blank=True, related_name="assignment_targets")
    functional_group = models.ForeignKey(FunctionalGroup, on_delete=models.PROTECT, null=True, blank=True, related_name="assignment_targets")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=(
            models.Q(target_type="employee", employee__isnull=False, position__isnull=True, org_unit__isnull=True, functional_group__isnull=True)
            | models.Q(target_type="position", employee__isnull=True, position__isnull=False, org_unit__isnull=True, functional_group__isnull=True)
            | models.Q(target_type="org_unit", employee__isnull=True, position__isnull=True, org_unit__isnull=False, functional_group__isnull=True)
            | models.Q(target_type="functional_group", employee__isnull=True, position__isnull=True, org_unit__isnull=True, functional_group__isnull=False)
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
