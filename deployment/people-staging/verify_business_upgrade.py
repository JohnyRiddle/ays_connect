"""Append-only upgrade from the checkpoint schema, synthetic business graph only."""
import os, sys
sys.path.insert(0,'/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
from django.conf import settings
assert os.environ.get('PEOPLE_ACCEPTANCE_MODE')=='1'
assert settings.DATABASES['default']['NAME']=='people_acceptance'
assert settings.DATABASES['default']['HOST']=='db'
target=os.environ.get('PEOPLE_BUSINESS_UPGRADE_DB','people_business_upgrade_20260908a')
assert target in {'people_business_upgrade_20260908a','people_business_upgrade_20260908b','people_business_upgrade_20260908c','people_business_upgrade_20260908d','people_business_upgrade_20260915e'}
settings.DATABASES['default']['NAME']=target
import django
django.setup()
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone
executor=MigrationExecutor(connection)
assert not executor.loader.applied_migrations,'Only a new empty database is accepted'
latest=executor.loader.graph.leaf_nodes()
previous=[(app, {'accounts':'0002_initial','work_tasks':'0003_alter_task_source_type_taskrecurrencerule_and_more'}.get(app,name)) for app,name in latest]
executor.migrate(previous)
old=executor.loader.project_state(previous).apps
saved=[]
def create(app,model_name,**values):
    obj=old.get_model(app,model_name).objects.create(**values)
    saved.append((app,model_name,obj.pk))
    return obj
user=create('accounts','User',username='upgrade-business',email='upgrade-business@example.test',password='!',is_active=False)
unit=create('organizations','OrgUnit',name='Synthetic upgrade unit')
employee=create('employees','Employee',user=user,employee_number='UPGRADE-BUSINESS',first_name='Synthetic',org_unit=unit)
create('employees','EmployeeProfile',employee=employee,bio='Synthetic retained profile')
role=create('access_control','Role',code='upgrade-business',name='Synthetic read only')
permission=create('access_control','Permission',code='task.view',name='View')
create('access_control','RolePermission',role=role,permission=permission,scope='own')
create('access_control','EmployeeRole',role=role,employee=employee,is_active=False)
task=create('work_tasks','Task',number='TASK-UPGRADE',title='Synthetic task',author=employee,
    responsible_employee=employee,executor_employee=employee,created_by=user,updated_by=user,org_unit=unit)
template=create('employees','OnboardingTemplate',name='Synthetic template',created_by=user)
version=create('employees','OnboardingTemplateVersion',template=template,number=1,name_snapshot='Synthetic template',published_by=user)
step_template=create('employees','OnboardingTemplateStep',version=version,key='work',title='Work',step_type='manual',position=1)
instance=create('employees','OnboardingInstance',employee=employee,template_version=version,assigned_by=user,status='active')
create('employees','OnboardingStepInstance',onboarding=instance,template_step=step_template,title_snapshot='Work',task=task,responsible_employee=employee)
category=create('service_requests','ServiceCategory',name='Synthetic category')
service=create('service_requests','Service',name='Synthetic service',category=category)
request_type=create('service_requests','RequestType',code='upgrade-business',name='Synthetic request',service=service,created_by=employee)
schema=create('service_requests','RequestTypeSchemaVersion',request_type=request_type,version=1,schema_json={},created_by=employee)
request=create('service_requests','ServiceRequest',number='REQ-UPGRADE',subject='Synthetic request',request_type=request_type,
    schema_version=schema,requester=employee,created_by=user,updated_by=user,service=service,category=category,
    assigned_employee=employee,responsible_employee=employee,org_unit=unit)
create('service_requests','ServiceRequestTask',request=request,task=task,created_by=user)
create('events','OutboxEvent',event_type='synthetic.upgrade',entity_type='Task',entity_id=str(task.pk),occurred_at=timezone.now(),payload={'task_id':str(task.pk)})
before={(app,name,str(pk)):old.get_model(app,name).objects.filter(pk=pk).values().get() for app,name,pk in saved}
published=create('work_tasks','Task',number='TASK-UPGRADE-PUBLISHED',title='Published',author=employee,
    created_by=user,updated_by=user,status='in_progress',acceptance_policy='author')
reopened=create('work_tasks','Task',number='TASK-UPGRADE-HISTORY',title='Historical publication',author=employee,
    created_by=user,updated_by=user,status='draft',acceptance_policy='author')
create('work_tasks','TaskStatusHistory',task=reopened,from_status='draft',to_status='assigned',actor=employee)
before={(app,name,str(pk)):old.get_model(app,name).objects.filter(pk=pk).values().get() for app,name,pk in saved}
MigrationExecutor(connection).migrate(latest)
from django.apps import apps
for app,name,pk in saved:
    current=apps.get_model(app,name).objects.filter(pk=pk).values().get()
    for field,value in before[(app,name,str(pk))].items():assert current[field]==value,(app,name,field)
assert apps.get_model('accounts','User').objects.get(pk=user.pk).auth_version==0
assert not MigrationExecutor(connection).migration_plan(latest)
from work_tasks.models import Task
from work_tasks.exceptions import TaskValidationError
assert not Task.objects.get(pk=task.pk).acceptance_policy_locked
for pk in (published.pk,reopened.pk):
    assert Task.objects.get(pk=pk).acceptance_policy_locked
    try: Task.objects.filter(pk=pk).update(acceptance_policy='none',title='Must rollback')
    except TaskValidationError as exc: assert exc.code=='task_acceptance_policy_frozen'
    else: raise AssertionError('Upgrade policy guard bypass')
    assert Task.objects.get(pk=pk).acceptance_policy=='author'
print(f'business_upgrade=PASS preserved_objects={len(saved)} repeat_migrate=NOOP policy_backfill_and_guard=PASS')
