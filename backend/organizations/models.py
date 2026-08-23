from django.conf import settings
from django.db import models
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
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=64, blank=True, null=True, unique=True)
    parent = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="children")
    legal_entity = models.ForeignKey(LegalEntity, on_delete=models.PROTECT, null=True, blank=True, related_name="org_units")
    unit_type = models.CharField(max_length=64, blank=True)
    manager_position = models.ForeignKey("employees.Position", on_delete=models.SET_NULL, null=True, blank=True, related_name="managed_org_units")
    manager_employee = models.ForeignKey("employees.Employee", on_delete=models.SET_NULL, null=True, blank=True, related_name="managed_org_units")

    class Meta:
        indexes = [models.Index(fields=["parent"]), models.Index(fields=["legal_entity"])]
        constraints = [models.CheckConstraint(condition=~models.Q(id=models.F("parent_id")), name="org_unit_parent_not_self")]

    def __str__(self):
        return self.name


class Location(TimestampedUUIDModel):
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=64, blank=True, null=True, unique=True)
    parent = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="children")
    legal_entity = models.ForeignKey(LegalEntity, on_delete=models.PROTECT, null=True, blank=True, related_name="locations")
    location_type = models.CharField(max_length=64, blank=True)

    class Meta:
        indexes = [models.Index(fields=["parent"]), models.Index(fields=["legal_entity"])]
        constraints = [models.CheckConstraint(condition=~models.Q(id=models.F("parent_id")), name="location_parent_not_self")]

    def __str__(self):
        return self.name

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
