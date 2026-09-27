"""Upgrade a fresh synthetic database from accepted People schema to Projects."""
import os
import sys
sys.path.insert(0,"/app")
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
from django.conf import settings
assert os.environ.get("PEOPLE_ACCEPTANCE_MODE")=="1"
assert settings.DATABASES["default"]["NAME"]=="projects_acceptance"
assert settings.DATABASES["default"]["HOST"]=="db"
target=os.environ.get("PROJECTS_UPGRADE_DB")
assert target in {"projects_upgrade_20260915","projects_upgrade_final_20260915"}
settings.DATABASES["default"]["NAME"]=target
import django
django.setup()
from django.apps import apps
from django.db import connection, IntegrityError, transaction
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

executor=MigrationExecutor(connection)
assert not executor.loader.applied_migrations,"Only an empty synthetic upgrade DB is allowed"
latest=executor.loader.graph.leaf_nodes()
previous=[node for node in latest if node[0]!="projects"]
executor.migrate(previous)
old=executor.loader.project_state(previous).apps
user=old.get_model("accounts","User").objects.create(username="synthetic-projects-upgrade",email="upgrade@example.test",password="!",is_active=False)
employee=old.get_model("employees","Employee").objects.create(user=user,first_name="Synthetic preserved employee")
task=old.get_model("work_tasks","Task").objects.create(number="TASK-PROJECTS-UPGRADE",title="Preserved Work task",author=employee,
    created_by=user,updated_by=user,status="in_progress",acceptance_policy="author")
before={"user":old.get_model("accounts","User").objects.filter(pk=user.pk).values().get(),
        "employee":old.get_model("employees","Employee").objects.filter(pk=employee.pk).values().get(),
        "task":old.get_model("work_tasks","Task").objects.filter(pk=task.pk).values().get()}
MigrationExecutor(connection).migrate(latest)
for label,app,model,pk in (("user","accounts","User",user.pk),("employee","employees","Employee",employee.pk),
                           ("task","work_tasks","Task",task.pk)):
    after=apps.get_model(app,model).objects.filter(pk=pk).values().get()
    assert after==before[label],(label,"changed on migration")
from projects.models import Project, ProjectStage, ProjectTaskLink
from work_tasks.models import Task
assert not ProjectTaskLink.objects.filter(task_id=task.pk).exists()
project=Project.objects.create(number="PRJ-UPGRADE-SYNTHETIC",name="Synthetic upgraded project",manager_id=employee.pk,
    created_by_id=user.pk,updated_by_id=user.pk)
other=Project.objects.create(number="PRJ-UPGRADE-OTHER",name="Other",created_by_id=user.pk,updated_by_id=user.pk)
wrong=ProjectStage.objects.create(project=other,name="Wrong")
try:
    with transaction.atomic():
        ProjectTaskLink.objects.create(project=project,stage=wrong,task_id=task.pk,linked_by_id=user.pk)
except IntegrityError:
    pass
else:
    raise AssertionError("Stage/project DB guard failed after upgrade")
assert not ProjectTaskLink.objects.filter(task_id=task.pk).exists()
assert not MigrationExecutor(connection).migration_plan(latest)
print("projects_upgrade=PASS preserved_people_work=3 unlinked_task=PASS stage_guard=PASS repeat_migrate=NOOP")
