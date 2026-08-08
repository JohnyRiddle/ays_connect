from django.conf import settings
from django.db import models

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
