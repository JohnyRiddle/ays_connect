"""Read-only DB comparison and isolated synthetic media-copy rehearsal."""
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0,'/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from django.apps import apps
from django.conf import settings
from django.db import connections

assert os.environ.get('PEOPLE_ACCEPTANCE_MODE')=='1'
assert settings.DATABASES['default']['NAME']=='people_acceptance'
assert settings.DATABASES['default']['HOST']=='db'
target=os.environ.get('PEOPLE_BUSINESS_RESTORE_DB','people_business_restore_20260908a')
assert target in {'people_business_restore_20260908a','people_business_restore_20260908b','people_business_restore_20260908c','people_business_restore_20260915d'}
config=connections.databases['default'].copy();config['NAME']=target
connections.databases['restore']=config

def fingerprint(alias):
    result={}
    for model in apps.get_models(include_auto_created=True):
        if not model._meta.managed or model._meta.proxy:continue
        fields=[field.attname for field in model._meta.concrete_fields]
        rows=list(model.objects.using(alias).order_by(model._meta.pk.attname).values_list(*fields))
        result[model._meta.db_table]=(len(rows),hashlib.sha256(json.dumps(rows,default=str,sort_keys=True).encode()).hexdigest())
    return result

source=fingerprint('default');restored=fingerprint('restore')
assert source==restored,'Synthetic restored DB differs from frozen source'
root=Path('/staging-private')/target.replace('people_business_restore_','business-restore-')
root.mkdir(exist_ok=False)
source_media=Path(settings.MEDIA_ROOT)
shutil.copytree(source_media,root/'backup-media')
shutil.copytree(root/'backup-media',root/'restored-media')
def media_hash(folder):
    return {str(path.relative_to(folder)):hashlib.sha256(path.read_bytes()).hexdigest()
            for path in folder.rglob('*') if path.is_file()}
assert media_hash(source_media)==media_hash(root/'restored-media')
from django.db import transaction, IntegrityError
from work_tasks.models import Task
from work_tasks.exceptions import TaskValidationError
locked=Task.objects.using('restore').filter(acceptance_policy_locked=True).first()
assert locked is not None,'A published synthetic task is required'
changed='author' if locked.acceptance_policy=='none' else 'none'
try: Task.objects.using('restore').filter(pk=locked.pk).update(acceptance_policy=changed,title='Must rollback')
except TaskValidationError as exc: assert exc.code=='task_acceptance_policy_frozen'
else: raise AssertionError('Restored ORM policy guard bypass')
try:
    with transaction.atomic(using='restore'), connections['restore'].cursor() as cursor:
        cursor.execute('UPDATE work_tasks_task SET acceptance_policy=%s WHERE id=%s',[changed,locked.pk])
except IntegrityError as exc: assert 'task_acceptance_policy_frozen' in str(exc)
else: raise AssertionError('Restored SQL policy guard bypass')
assert fingerprint('restore')==source,'Guard failure changed restored data'
print(json.dumps({'business_restore':'PASS','tables':len(source),'rows':sum(v[0] for v in source.values()),
                  'media_files':len(media_hash(source_media)),'all_fields_relations_auth_version_equal':True,
                  'source_database_overwritten':False,'restored_orm_and_sql_policy_guard':'PASS'}))
