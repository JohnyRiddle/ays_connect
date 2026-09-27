"""Create synthetic local staging actors; keep generated passwords inside the private volume."""
import json
import os
import secrets
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from access_control.models import EmployeeRole, Permission, Role, RolePermission
from employees.models import AssignmentTarget, Employee
from work_tasks.services import TaskService


def ensure_executor(fixture):
    if "executor" in fixture["actors"]:
        return fixture
    password=secrets.token_urlsafe(32)
    email="synthetic-projects-executor@example.test"
    user,_=get_user_model().objects.get_or_create(username="synthetic-projects-executor",defaults={"email":email})
    user.set_password(password);user.save(update_fields=["password"])
    employee,_=Employee.objects.get_or_create(user=user,defaults={"first_name":"Synthetic executor"})
    role,_=Role.objects.get_or_create(code="synthetic-projects-executor",defaults={"name":"Synthetic Work executor"})
    for code in ("task.view","task.start","task.complete"):
        RolePermission.objects.get_or_create(role=role,permission=Permission.objects.get(code=code),defaults={"scope":"own"})
    EmployeeRole.objects.get_or_create(employee=employee,role=role)
    target,_=AssignmentTarget.objects.get_or_create(target_type="employee",employee=employee)
    fixture["actors"]["executor"]={"email":email,"password":password,"employee":str(employee.pk)}
    fixture["executor_target"]=str(target.pk)
    return fixture


class Command(BaseCommand):
    help = "Seed local Projects staging with synthetic employees and Work tasks."

    def handle(self, *args, **options):
        if os.environ.get("PEOPLE_ACCEPTANCE_MODE") != "1" or settings.DATABASES["default"]["NAME"] != "projects_acceptance":
            raise RuntimeError("This seed is restricted to the isolated Projects acceptance database.")
        path = Path("/staging-private/projects-fixture.json")
        if path.exists():
            role=Role.objects.get(code="synthetic-projects-acceptance")
            RolePermission.objects.get_or_create(role=role,permission=Permission.objects.get(code="employee.view"),
                defaults={"scope":"global"})
            fixture=json.loads(path.read_text(encoding="utf-8"))
            with transaction.atomic(): fixture=ensure_executor(fixture)
            path.write_text(json.dumps(fixture),encoding="utf-8")
            path.chmod(0o600)
            self.stdout.write("projects_fixture=EXISTS")
            return
        with transaction.atomic():
            role = Role.objects.create(code="synthetic-projects-acceptance", name="Synthetic Projects acceptance")
            codes = ("project.view", "project.create", "project.edit", "project.members_manage",
                "project.structure_manage", "project.task_link_manage", "project.lifecycle", "project.comment",
                "project.attachment_add", "project.attachment_delete", "task.view", "task.create", "task.edit",
                "task.assign", "task.start", "task.complete", "task.accept", "task.reopen", "employee.view")
            for code in codes:
                permission = Permission.objects.get(code=code)
                RolePermission.objects.create(role=role, permission=permission, scope="global")
            actors = {}
            for label in ("manager", "outsider"):
                password = secrets.token_urlsafe(32)
                email = f"synthetic-projects-{label}@example.test"
                user = get_user_model().objects.create_user(username=f"synthetic-projects-{label}", email=email, password=password)
                employee = Employee.objects.create(user=user, first_name=f"Synthetic {label}")
                if label == "manager": EmployeeRole.objects.create(employee=employee, role=role)
                actors[label] = {"email": email, "password": password, "employee": str(employee.pk)}
            manager = Employee.objects.get(pk=actors["manager"]["employee"])
            target = AssignmentTarget.objects.create(target_type="employee", employee=manager)
            task = TaskService.create(actor=manager, actor_user=manager.user, title="Synthetic existing Work task",
                                      responsible_target=target, executor_target=target, acceptance_policy="author")
            fixture = ensure_executor({"actors": actors, "existing_task": str(task.pk), "target": str(target.pk)})
        path.write_text(json.dumps(fixture), encoding="utf-8")
        path.chmod(0o600)
        self.stdout.write("projects_fixture=CREATED synthetic_accounts=3 synthetic_tasks=1")
