from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    email = models.EmailField("электронная почта", unique=True)
    phone = models.CharField("телефон", max_length=32, blank=True, unique=True, null=True)
    middle_name = models.CharField("отчество", max_length=150, blank=True)
    is_demo = models.BooleanField(default=False)
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

class Role(models.Model):
    class Code(models.TextChoices):
        EMPLOYEE = "employee", "Сотрудник"
        TECHNICIAN = "technician", "Технический специалист"
        MANAGER = "manager", "Руководитель"
        FACILITY_MANAGER = "facility_manager", "Управляющий объектом"
        HR = "hr", "HR"
        ADMIN = "admin", "Администратор"
        EXECUTIVE = "executive", "Руководитель компании"
        OWNER = "owner", "Собственник"
        OBSERVER = "observer", "Наблюдатель"
        AUDITOR = "auditor", "Аудитор"
    code = models.CharField(max_length=32, choices=Code.choices, unique=True)
    name = models.CharField(max_length=100)
    def __str__(self): return self.name

class UserRole(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="role_assignments")
    role = models.ForeignKey(Role, on_delete=models.PROTECT)
    company = models.ForeignKey("organizations.Company", on_delete=models.CASCADE, null=True, blank=True)
    facility = models.ForeignKey("organizations.Facility", on_delete=models.CASCADE, null=True, blank=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "role", "company", "facility"], name="unique_user_role_scope")]
