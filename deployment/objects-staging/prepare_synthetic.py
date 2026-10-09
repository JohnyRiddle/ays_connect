"""Synthetic-only setup for the dedicated objects PostgreSQL; never production."""
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from django.db import connection, transaction
from accounts.models import User
from employees.models import Employee
from access_control.models import Permission, Role, RolePermission, EmployeeRole
from organizations.models import LegalEntity, OrgUnit
from service_requests.models import ServiceCategory, Service, RequestType
from service_requests.services import SchemaService

assert connection.vendor == "postgresql" and connection.settings_dict["NAME"] == "objects", "Dedicated synthetic DB only"

with transaction.atomic():
    legal, _ = LegalEntity.objects.get_or_create(code="SYNTHETIC-OBJECTS", defaults={"name": "Синтетическое юрлицо"})
    unit, _ = OrgUnit.objects.get_or_create(code="SYNTHETIC-OBJECTS", defaults={"name": "Синтетическое подразделение", "legal_entity": legal})
    user, _ = User.objects.get_or_create(email="objects@synthetic.test", defaults={"username": "objects-synthetic"})
    user.set_password("SyntheticObjectsOnly1!")
    user.save()
    actor, _ = Employee.objects.get_or_create(user=user, defaults={"first_name": "Синтетический", "last_name": "Оператор", "is_demo": True, "legal_entity": legal, "org_unit": unit})
    manager, _ = Employee.objects.get_or_create(work_email="objects-manager@synthetic.test", defaults={"first_name": "Синтетический", "last_name": "Управляющий", "is_demo": True, "legal_entity": legal, "org_unit": unit})
    role, _ = Role.objects.get_or_create(code="SYNTHETIC-OBJECTS", defaults={"name": "Синтетический оператор Objects"})
    for code in ["location.view", "location.create", "location.edit", "location.manage_zones", "location.assign_responsible", "location.change_status", "location.archive", "location.restore", "location.move", "organization.view", "people.directory.view", "people.profile.view_self", "employee.view", "task.view", "task.create", "task.edit", "request.create", "request.view", "service_catalog.view", "request_type.publish", "project.view", "project.create"]:
        permission, _ = Permission.objects.get_or_create(code=code, defaults={"name": code})
        RolePermission.objects.get_or_create(role=role, permission=permission, scope="global")
    EmployeeRole.objects.get_or_create(employee=actor, role=role, defaults={"is_active": True})
    category, _ = ServiceCategory.objects.get_or_create(name="Синтетическая категория Objects")
    service, _ = Service.objects.get_or_create(category=category, name="Синтетическая услуга Objects")
    request_type, _ = RequestType.objects.get_or_create(code="SYNTHETIC-OBJECTS", defaults={"service": service, "name": "Синтетическая заявка", "created_by": actor})
    if not request_type.current_schema_version_id:
        SchemaService.publish(request_type, actor, user)
    denied, _ = User.objects.get_or_create(email="objects-denied@synthetic.test", defaults={"username": "objects-denied"})
    denied.set_password("SyntheticObjectsOnly1!")
    denied.save()
    Employee.objects.get_or_create(user=denied, defaults={"first_name": "Синтетический", "last_name": "Без прав", "is_demo": True})
    editor, _ = User.objects.get_or_create(email="objects-editor@synthetic.test", defaults={"username":"objects-editor"})
    editor.set_password("SyntheticObjectsOnly1!")
    editor.save()
    person, _ = Employee.objects.get_or_create(user=editor, defaults={"first_name":"Синтетический", "last_name":"Редактор без HR", "is_demo":True})
    editor_role, _ = Role.objects.get_or_create(code="SYNTHETIC-OBJECTS-EDITOR", defaults={"name":"Синтетический редактор без организации"})
    for code in ("location.view", "location.edit"):
        RolePermission.objects.get_or_create(role=editor_role,permission=Permission.objects.get(code=code),scope="global")
    EmployeeRole.objects.get_or_create(employee=person,role=editor_role,defaults={"is_active":True})
print("Synthetic Objects personas and catalog prepared; no real users or legacy objects created.")
