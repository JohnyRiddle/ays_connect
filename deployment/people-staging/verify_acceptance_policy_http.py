"""Real HTTP acceptance invariant smoke, isolated synthetic identity only."""
import os,sys,json,uuid,urllib.request,urllib.error
sys.path.insert(0,'/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from django.conf import settings
from django.db import transaction
from accounts.models import User
from accounts.serializers import EmailTokenSerializer
from access_control.models import Role,Permission,RolePermission
from access_control.services import RoleService
from employees.models import Employee,AssignmentTarget
from work_tasks.models import Task
from audit.models import AuditEvent
assert os.environ.get('PEOPLE_ACCEPTANCE_MODE')=='1'
assert settings.DATABASES['default']['NAME']=='people_acceptance' and settings.DATABASES['default']['HOST']=='db'
assert os.environ.get('DJANGO_SECRET_KEY')
run=uuid.uuid4().hex[:10]
with transaction.atomic():
    user=User.objects.create_user(username='policy-'+run,email='policy-'+run+'@example.test',password=None)
    assert user.pk!=2
    employee=Employee.objects.create(user=user,first_name='Synthetic policy')
    role=Role.objects.create(code='policy-'+run,name='Synthetic policy smoke')
    for code in ['task.create','task.view','task.edit','task.assign']:
        RolePermission.objects.create(role=role,permission=Permission.objects.get(code=code),scope='global')
    RoleService.assign_role(employee=employee,role=role)
    target=AssignmentTarget.objects.create(target_type='employee',employee=employee)
access=str(EmailTokenSerializer.get_token(user).access_token)
def request(path,method,data):
    req=urllib.request.Request('http://127.0.0.1:8000'+path,data=json.dumps(data).encode(),
        headers={'Authorization':'Bearer '+access,'Content-Type':'application/json'},method=method)
    try:
        with urllib.request.urlopen(req,timeout=10) as response:return response.status,json.loads(response.read())
    except urllib.error.HTTPError as error:return error.code,json.loads(error.read())
code,body=request('/api/internal/v1/tasks/','POST',{'title':'Synthetic policy','responsible_target':str(target.pk),'acceptance_policy':'none'})
assert code==201
pk=body['id'];path=f'/api/internal/v1/tasks/{pk}/'
code,body=request(path,'PATCH',{'version':body['version'],'acceptance_policy':'author'})
assert code==200 and body['acceptance_policy']=='author'
code,body=request(path+'publish/','POST',{'version':body['version']})
assert code==200
version=body['version'];audit_count=AuditEvent.objects.filter(entity_id=pk).count()
code,body=request(path,'PATCH',{'version':version,'acceptance_policy':'none','title':'Forbidden'})
assert code==400 and body['error']['code']=='task_acceptance_policy_frozen'
task=Task.objects.get(pk=pk)
assert task.title=='Synthetic policy' and task.acceptance_policy=='author' and task.version==version
assert AuditEvent.objects.filter(entity_id=pk).count()==audit_count
code,body=request(path,'PATCH',{'version':version,'acceptance_policy':'author'})
assert code==200 and body['version']==version
assert AuditEvent.objects.filter(entity_id=pk,action='task.updated').get().actor_id==user.pk
assert not user.is_staff and not user.is_superuser and not user.has_usable_password()
print('acceptance_policy_http=PASS draft_edit=PASS published_reject=PASS atomic=PASS noop=PASS actor=PASS')
