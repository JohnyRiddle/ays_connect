from django.conf import settings
from django.db import models

class Employee(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Работает"
        VACATION = "vacation", "Отпуск"
        SICK = "sick", "Больничный"
        ARCHIVED = "archived", "Архив"
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="employee")
    company = models.ForeignKey("organizations.Company", on_delete=models.PROTECT, related_name="employees")
    department = models.ForeignKey("organizations.Department", on_delete=models.SET_NULL, null=True, related_name="employees")
    manager = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="reports")
    employee_number = models.CharField(max_length=30, unique=True)
    position = models.CharField(max_length=150)
    hire_date = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    work_schedule = models.CharField(max_length=100, default="5/2, 09:00–18:00")
    skills = models.JSONField(default=list, blank=True)
    is_demo = models.BooleanField(default=False)
    facilities = models.ManyToManyField("organizations.Facility", through="EmployeeFacility", related_name="employees")
    def __str__(self): return f"{self.employee_number} — {self.position}"
    class Meta: ordering = ["user__last_name", "user__first_name"]

class EmployeeFacility(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    facility = models.ForeignKey("organizations.Facility", on_delete=models.CASCADE)
    is_primary = models.BooleanField(default=False)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["employee", "facility"], name="unique_employee_facility")]
