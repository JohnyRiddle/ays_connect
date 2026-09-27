"""Read-only fingerprints and DB guard probe after restoring a synthetic Projects upgrade dump."""
import hashlib
import os
import sys
sys.path.insert(0,"/app")
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
import django
django.setup()
from django.conf import settings
from django.db import connections, transaction, IntegrityError
assert os.environ.get("PEOPLE_ACCEPTANCE_MODE")=="1"
assert settings.DATABASES["default"]["NAME"]=="projects_acceptance"
assert settings.DATABASES["default"]["HOST"]=="db"
source_name=os.environ.get("PROJECTS_UPGRADE_DB","projects_upgrade_20260915")
restore_name=os.environ.get("PROJECTS_RESTORE_DB","projects_restore_20260915")
assert (source_name,restore_name) in {("projects_upgrade_20260915","projects_restore_20260915"),
    ("projects_upgrade_final_20260915","projects_restore_final_20260915")}
for alias,name in (("upgrade",source_name),("restore",restore_name)):
    config=connections.databases["default"].copy();config["NAME"]=name
    connections.databases[alias]=config

def fingerprint(alias):
    with connections[alias].cursor() as cursor:
        cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
        tables=[item[0] for item in cursor.fetchall()]
        result={}
        for table in tables:
            cursor.execute(f'SELECT row_to_json(t)::text FROM "{table}" t')
            rows=sorted(item[0] for item in cursor.fetchall())
            result[table]=(len(rows),hashlib.sha256("\n".join(rows).encode()).hexdigest())
    return result

source=fingerprint("upgrade")
restored=fingerprint("restore")
assert source==restored,"Restored synthetic business rows differ"
from projects.models import Project, ProjectStage, ProjectTaskLink
from work_tasks.models import Task
task=Task.objects.using("restore").get(number="TASK-PROJECTS-UPGRADE")
project=Project.objects.using("restore").get(number="PRJ-UPGRADE-SYNTHETIC")
stage=ProjectStage.objects.using("restore").get(name="Wrong")
assert task.acceptance_policy_locked and not ProjectTaskLink.objects.using("restore").filter(task=task).exists()
try:
    with transaction.atomic(using="restore"):
        ProjectTaskLink.objects.using("restore").create(project=project,stage=stage,task=task,linked_by_id=project.created_by_id)
except IntegrityError:
    pass
else:
    raise AssertionError("Restored stage/project guard failed")
try:
    with transaction.atomic(using="restore"):
        Project.objects.using("restore").filter(pk=project.pk).update(number="PRJ-RESTORE-BYPASS")
except IntegrityError:
    pass
else:
    raise AssertionError("Restored immutable number guard failed")
assert fingerprint("restore")==source,"Guard probe changed restored DB"
print(f"projects_restore=PASS tables={len(source)} rows={sum(value[0] for value in source.values())} preserved_work=PASS stage_guard=PASS number_guard=PASS")
