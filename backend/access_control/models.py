import uuid
from django.db import models


class Scope(models.TextChoices):
    OWN = "own", "Собственные"
    PARTICIPATING = "participating", "С участием"
    TEAM = "team", "Команда"
    ORG_UNIT = "org_unit", "Подразделение"
    LEGAL_ENTITY = "legal_entity", "Юридическое лицо"
    GLOBAL = "global", "Глобально"


class Permission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=120, unique=True)
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.code


class Role(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class RolePermission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="permission_grants")
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, related_name="role_grants")
    scope = models.CharField(max_length=24, choices=Scope.choices)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["role", "permission", "scope"], name="unique_role_permission_scope")]


class EmployeeRole(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="access_roles")
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name="employee_assignments")
    org_unit = models.ForeignKey("organizations.OrgUnit", on_delete=models.PROTECT, null=True, blank=True, related_name="employee_roles")
    legal_entity = models.ForeignKey("organizations.LegalEntity", on_delete=models.PROTECT, null=True, blank=True, related_name="employee_roles")
    location = models.ForeignKey("organizations.Location", on_delete=models.PROTECT, null=True, blank=True, related_name="employee_roles")
    active_from = models.DateTimeField(null=True, blank=True)
    active_until = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["employee"]), models.Index(fields=["role"])]
        constraints = [models.UniqueConstraint(fields=["employee", "role", "org_unit", "legal_entity", "location"], condition=models.Q(is_active=True), name="unique_active_employee_role_context")]
