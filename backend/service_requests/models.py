import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class UUIDTimeModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta: abstract = True


class ServiceCategory(UUIDTimeModel):
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=64, null=True, blank=True, unique=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="children")
    position = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)
    class Meta:
        ordering = ["position", "name", "id"]
        constraints = [models.CheckConstraint(condition=~models.Q(id=models.F("parent_id")), name="service_category_parent_not_self")]
    def __str__(self): return self.name


class Service(UUIDTimeModel):
    category = models.ForeignKey(ServiceCategory, on_delete=models.PROTECT, related_name="services")
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=64, null=True, blank=True, unique=True)
    description = models.TextField(blank=True)
    owner_org_unit = models.ForeignKey("organizations.OrgUnit", on_delete=models.PROTECT, null=True, blank=True, related_name="owned_services")
    owner_functional_group = models.ForeignKey("employees.FunctionalGroup", on_delete=models.PROTECT, null=True, blank=True, related_name="owned_services")
    legal_entity = models.ForeignKey("organizations.LegalEntity", on_delete=models.PROTECT, null=True, blank=True, related_name="services")
    location = models.ForeignKey("organizations.Location", on_delete=models.PROTECT, null=True, blank=True, related_name="services")
    position = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)
    class Meta: ordering = ["position", "name", "id"]
    def __str__(self): return self.name


class RequestType(UUIDTimeModel):
    class Priority(models.TextChoices):
        LOW="low", "Low"; NORMAL="normal", "Normal"; HIGH="high", "High"; CRITICAL="critical", "Critical"
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="request_types")
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    instructions = models.TextField(blank=True)
    default_priority = models.CharField(max_length=16, choices=Priority.choices, default=Priority.NORMAL)
    position = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)
    allow_anonymous_employee = models.BooleanField(default=False)
    allow_self_service = models.BooleanField(default=True)
    created_by = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="created_request_types")
    current_schema_version = models.OneToOneField("RequestTypeSchemaVersion", on_delete=models.PROTECT, null=True, blank=True, related_name="current_for_type")
    class Meta: ordering = ["position", "name", "id"]
    def __str__(self): return self.name


class AccessScope(models.TextChoices):
    GLOBAL="global", "Global"; LEGAL_ENTITY="legal_entity", "Legal entity"; ORG_UNIT="org_unit", "Org unit"; LOCATION="location", "Location"; ROLE="role", "Role"


class RequestTypeAccessRule(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request_type = models.ForeignKey(RequestType, on_delete=models.CASCADE, related_name="access_rules")
    scope_type = models.CharField(max_length=24, choices=AccessScope.choices)
    legal_entity = models.ForeignKey("organizations.LegalEntity", on_delete=models.PROTECT, null=True, blank=True)
    org_unit = models.ForeignKey("organizations.OrgUnit", on_delete=models.PROTECT, null=True, blank=True)
    location = models.ForeignKey("organizations.Location", on_delete=models.PROTECT, null=True, blank=True)
    role = models.ForeignKey("access_control.Role", on_delete=models.PROTECT, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["created_at", "id"]
        constraints = [models.CheckConstraint(condition=(
            models.Q(scope_type="global",legal_entity__isnull=True,org_unit__isnull=True,location__isnull=True,role__isnull=True)
            | models.Q(scope_type="legal_entity",legal_entity__isnull=False,org_unit__isnull=True,location__isnull=True,role__isnull=True)
            | models.Q(scope_type="org_unit",legal_entity__isnull=True,org_unit__isnull=False,location__isnull=True,role__isnull=True)
            | models.Q(scope_type="location",legal_entity__isnull=True,org_unit__isnull=True,location__isnull=False,role__isnull=True)
            | models.Q(scope_type="role",legal_entity__isnull=True,org_unit__isnull=True,location__isnull=True,role__isnull=False)
        ),name="request_access_rule_exact_target")]


class FieldType(models.TextChoices):
    TEXT="text", "Text"; TEXTAREA="textarea", "Textarea"; INTEGER="integer", "Integer"; DECIMAL="decimal", "Decimal"; BOOLEAN="boolean", "Boolean"; DATE="date", "Date"; DATETIME="datetime", "Datetime"; CHOICE="choice", "Choice"; MULTI_CHOICE="multi_choice", "Multiple choice"; EMPLOYEE="employee", "Employee"; ORG_UNIT="org_unit", "Org unit"; LEGAL_ENTITY="legal_entity", "Legal entity"; LOCATION="location", "Location"; FILE="file", "File"


class RequestFieldDefinition(UUIDTimeModel):
    request_type = models.ForeignKey(RequestType, on_delete=models.CASCADE, related_name="fields")
    key = models.SlugField(max_length=100)
    label = models.CharField(max_length=200)
    help_text = models.TextField(blank=True)
    field_type = models.CharField(max_length=24, choices=FieldType.choices)
    required = models.BooleanField(default=False)
    position = models.PositiveIntegerField(default=0)
    default_value = models.JSONField(null=True, blank=True)
    config = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    class Meta:
        ordering = ["position", "key", "id"]
        constraints = [models.UniqueConstraint(fields=["request_type", "key"], name="unique_request_field_key")]
    def __str__(self): return f"{self.request_type.code}.{self.key}"


class RequestFieldOption(UUIDTimeModel):
    field = models.ForeignKey(RequestFieldDefinition, on_delete=models.CASCADE, related_name="options")
    value = models.CharField(max_length=100)
    label = models.CharField(max_length=200)
    position = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)
    class Meta:
        ordering = ["position", "value", "id"]
        constraints = [models.UniqueConstraint(fields=["field", "value"], name="unique_request_field_option")]


class RequestTypeSchemaVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request_type = models.ForeignKey(RequestType, on_delete=models.PROTECT, related_name="schema_versions")
    version = models.PositiveIntegerField()
    schema_json = models.JSONField()
    created_by = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="published_request_schemas")
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["-version"]
        constraints = [models.UniqueConstraint(fields=["request_type", "version"], name="unique_request_schema_version")]
    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists(): raise ValidationError("Published schema versions are immutable.")
        return super().save(*args, **kwargs)
    def delete(self, *args, **kwargs): raise ValidationError("Published schema versions are immutable.")
