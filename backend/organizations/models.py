from django.conf import settings
from django.db import models
from django.utils import timezone
import uuid


class TimestampedUUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class LegalEntity(TimestampedUUIDModel):
    name = models.CharField(max_length=200)
    short_name = models.CharField(max_length=80, blank=True)
    code = models.CharField(max_length=64, blank=True, null=True, unique=True)

    def __str__(self):
        return self.short_name or self.name


class OrgUnit(TimestampedUUIDModel):
    class Type(models.TextChoices):
        COMPANY = "company", "Компания"
        DIRECTION = "direction", "Направление"
        DIVISION = "division", "Дивизион"
        DEPARTMENT = "department", "Отдел"
        BRANCH = "branch", "Филиал"
        FACILITY = "facility", "Объект"
        SECTION = "section", "Секция"
        OTHER = "other", "Другое"

    class Status(models.TextChoices):
        ACTIVE = "active", "Активно"
        CLOSED = "closed", "Закрыто"

    name = models.CharField(max_length=150)
    short_name = models.CharField(max_length=80, blank=True)
    description = models.TextField(blank=True)
    code = models.CharField(max_length=64, blank=True, null=True, unique=True)
    parent = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="children")
    legal_entity = models.ForeignKey(LegalEntity, on_delete=models.PROTECT, null=True, blank=True, related_name="org_units")
    unit_type = models.CharField(max_length=64, choices=Type.choices, default=Type.OTHER)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    valid_from = models.DateTimeField(default=timezone.now)
    valid_to = models.DateTimeField(null=True, blank=True)
    sort_order = models.IntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)
    version = models.PositiveIntegerField(default=1)
    manager_position = models.ForeignKey("employees.Position", on_delete=models.SET_NULL, null=True, blank=True, related_name="managed_org_units")
    manager_employee = models.ForeignKey("employees.Employee", on_delete=models.SET_NULL, null=True, blank=True, related_name="managed_org_units")

    class Meta:
        indexes = [models.Index(fields=["parent"]), models.Index(fields=["legal_entity"])]
        constraints = [
            models.CheckConstraint(condition=~models.Q(id=models.F("parent_id")), name="org_unit_parent_not_self"),
            models.CheckConstraint(condition=models.Q(valid_to__isnull=True) | models.Q(valid_to__gte=models.F("valid_from")), name="org_unit_valid_period"),
        ]

    def __str__(self):
        return self.name


class Location(TimestampedUUIDModel):
    class NodeKind(models.TextChoices):
        UNCLASSIFIED = "unclassified", "Не классифицировано"
        GEOGRAPHY = "geography", "География"
        SITE = "site", "Площадка"
        OBJECT = "object", "Объект"
        ZONE = "zone", "Зона"

    class BusinessType(models.TextChoices):
        RESTAURANT = "restaurant", "Ресторан"
        BAR = "bar", "Бар"
        NIGHTCLUB = "nightclub", "Ночной клуб"
        HOTEL = "hotel", "Отель"
        DORMITORY = "dormitory", "Общежитие"
        WAREHOUSE = "warehouse", "Склад"
        PRODUCTION = "production", "Производство"
        OFFICE = "office", "Офис"
        TECHNICAL = "technical", "Технический объект"
        OTHER = "other", "Другое"

    class BusinessStatus(models.TextChoices):
        PREPARATION = "preparation", "Подготовка"
        OPERATING = "operating", "Работает"
        SEASONAL_CLOSED = "seasonal_closed", "Сезонно закрыт"
        FINAL_CLOSED = "final_closed", "Окончательно закрыт"

    name = models.CharField(max_length=200)
    code = models.CharField(max_length=64, blank=True, null=True, unique=True)
    parent = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="children")
    legal_entity = models.ForeignKey(LegalEntity, on_delete=models.PROTECT, null=True, blank=True, related_name="locations")
    location_type = models.CharField(max_length=64, blank=True)
    node_kind = models.CharField(max_length=24, choices=NodeKind.choices, default=NodeKind.UNCLASSIFIED, db_index=True)
    business_type = models.CharField(max_length=24, choices=BusinessType.choices, blank=True)
    business_status = models.CharField(max_length=24, choices=BusinessStatus.choices, blank=True)
    address = models.CharField(max_length=500, blank=True)
    timezone = models.CharField(max_length=64, blank=True)
    org_unit = models.ForeignKey(OrgUnit, on_delete=models.PROTECT, null=True, blank=True, related_name="locations")
    contacts = models.CharField(max_length=1000, blank=True)
    work_schedule = models.CharField(max_length=1000, blank=True)
    description = models.TextField(blank=True, max_length=10000)
    is_archived = models.BooleanField(default=False, db_index=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        indexes = [models.Index(fields=["parent"]), models.Index(fields=["legal_entity"])]
        constraints = [models.CheckConstraint(condition=~models.Q(id=models.F("parent_id")), name="location_parent_not_self")]

    def __str__(self):
        return self.name


class LocationResponsibility(TimestampedUUIDModel):
    class Role(models.TextChoices):
        MANAGER = "manager", "Управляющий"
        TECHNICAL = "technical", "Технический ответственный"

    location = models.ForeignKey(Location, on_delete=models.PROTECT, related_name="responsibilities")
    employee = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="location_responsibilities")
    role = models.CharField(max_length=24, choices=Role.choices)
    valid_from = models.DateTimeField(default=timezone.now)
    valid_to = models.DateTimeField(null=True, blank=True)
    end_reason = models.CharField(max_length=500, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["location", "role"], condition=models.Q(valid_to__isnull=True), name="location_one_current_responsible"),
            models.CheckConstraint(condition=models.Q(valid_to__isnull=True) | models.Q(valid_to__gte=models.F("valid_from")), name="location_responsibility_period"),
        ]


class LocationIdempotency(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    operation = models.CharField(max_length=32)
    key = models.CharField(max_length=128)
    payload_hash = models.CharField(max_length=64)
    location = models.ForeignKey(Location, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["actor", "operation", "key"], name="location_idempotency_actor_operation_key")]

class Company(models.Model):
    name = models.CharField(max_length=200)
    short_name = models.CharField(max_length=80)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, default="active")
    timezone = models.CharField(max_length=64, default="Asia/Novosibirsk")
    is_demo = models.BooleanField(default=False)
    def __str__(self): return self.short_name

class Region(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="regions")
    name = models.CharField(max_length=150)
    timezone = models.CharField(max_length=64, default="Asia/Novosibirsk")
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    def __str__(self): return self.name

class Cluster(models.Model):
    region = models.ForeignKey(Region, on_delete=models.CASCADE, related_name="clusters")
    name = models.CharField(max_length=150)
    def __str__(self): return self.name

class Facility(models.Model):
    class Type(models.TextChoices):
        RESTAURANT = "restaurant", "Ресторан"
        HOTEL = "hotel", "Отель"
        OFFICE = "office", "Офис"
        WAREHOUSE = "warehouse", "Склад"
        PRODUCTION = "production", "Производство"
        TECHNICAL = "technical", "Технический объект"
    cluster = models.ForeignKey(Cluster, on_delete=models.CASCADE, related_name="facilities")
    name = models.CharField(max_length=200)
    facility_type = models.CharField(max_length=30, choices=Type.choices)
    address = models.CharField(max_length=300)
    work_schedule = models.CharField(max_length=100, blank=True)
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, default="active")
    description = models.TextField(blank=True)
    is_demo = models.BooleanField(default=False)
    def __str__(self): return self.name

class Department(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="departments")
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="children")
    name = models.CharField(max_length=150)
    def __str__(self): return self.name

class Zone(models.Model):
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE, related_name="zones")
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    def __str__(self): return self.name
