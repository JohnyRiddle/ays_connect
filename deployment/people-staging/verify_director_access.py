"""Explicit draft allowlist: synthetic staging only, no password/production identity."""
import json
import os
import sys
import uuid
import urllib.request
import urllib.error
sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.conf import settings
from django.db import transaction
from accounts.models import User
from accounts.serializers import EmailTokenSerializer
from access_control.models import Permission, Role, RolePermission
from access_control.services import RoleService
from employees.models import Employee, EmployeeProfile
from organizations.models import OrgUnit
from work_tasks.models import Task, TaskComment
from service_requests.models import ServiceCategory, Service, RequestType, RequestTypeSchemaVersion, ServiceRequest, ServiceRequestComment

# No wildcard, complement set or automatic future grants. Pending choices excluded.
ALLOWLIST = (
    'task.view', 'request.view', 'people.directory.view', 'organization.view',
    'location.view', 'people.team.view', 'service_catalog.view', 'request_type.view',
)
assert os.environ.get('PEOPLE_ACCEPTANCE_MODE') == '1'
assert os.environ.get('DJANGO_SECRET_KEY')
assert settings.DATABASES['default']['NAME'] == 'people_acceptance'
assert settings.DATABASES['default']['HOST'] == 'db'
suffix=uuid.uuid4().hex[:10]
with transaction.atomic():
    user=User.objects.create_user(username='matrix-'+suffix,email='matrix-'+suffix+'@example.test',password=None)
    director=Employee.objects.create(user=user,first_name='Synthetic director',employee_number='M-'+suffix)
    role=Role.objects.create(code='matrix-'+suffix,name='DRAFT synthetic business reader')
    for code in ALLOWLIST:
        RolePermission.objects.create(role=role,permission=Permission.objects.get(code=code),scope='global')
    RoleService.assign_role(employee=director,role=role)
    category=ServiceCategory.objects.create(name='Synthetic matrix '+suffix)
    service=Service.objects.create(category=category,name='Synthetic matrix')
    request_type=RequestType.objects.create(service=service,name='Synthetic matrix',code='M-'+suffix,created_by=director)
    schema=RequestTypeSchemaVersion.objects.create(request_type=request_type,version=1,schema_json={'fields':[]},created_by=director)
    subjects=[]
    for index in range(2):
        unit=OrgUnit.objects.create(name=f'Synthetic matrix {suffix} {index}')
        person=Employee.objects.create(first_name=f'Synthetic subject {index}',employee_number=f'M{index}-{suffix}',org_unit=unit)
        EmployeeProfile.objects.create(employee=person,additional_email='private@example.test',additional_email_visibility='private')
        task=Task.objects.create(number=f'MATRIX-{suffix}-{index}',title='Synthetic visibility',author=person,org_unit=unit,created_by=user,updated_by=user)
        item=ServiceRequest.objects.create(number=f'MATRIX-{suffix}-{index}',request_type=request_type,schema_version=schema,requester=person,created_by=user,updated_by=user,subject='Synthetic visibility',service=service,category=category,org_unit=unit)
        TaskComment.objects.create(task=task,author=person,body='SYNTHETIC_INTERNAL_MATRIX',is_internal=True)
        ServiceRequestComment.objects.create(request=item,author=person,body='SYNTHETIC_INTERNAL_MATRIX',visibility='internal')
        subjects.append((person,unit,task,item))
access=str(EmailTokenSerializer.get_token(user).access_token)
results=[]
def request(path,method='GET',data=None):
    req=urllib.request.Request('http://127.0.0.1:8000'+path,
        data=json.dumps(data).encode() if data is not None else None,
        headers={'Authorization':'Bearer '+access,'Content-Type':'application/json'},method=method)
    try:
        with urllib.request.urlopen(req,timeout=10) as response:
            body=response.read()
            try: payload=json.loads(body)
            except ValueError: payload={}
            return response.status,payload
    except urllib.error.HTTPError as error:
        try: payload=json.loads(error.read())
        except ValueError: payload={}
        return error.code,payload
def check(label,ok):
    results.append({'check':label,'status':'PASS' if ok else 'FAIL'})
    print(json.dumps(results[-1]),flush=True)
for index,(person,unit,task,item) in enumerate(subjects):
    check(f'task_cross_unit_{index}',request(f'/api/internal/v1/tasks/{task.pk}/')[0]==200)
    check(f'request_cross_unit_{index}',request(f'/api/internal/v1/requests/{item.pk}/')[0]==200)
    for domain,pk in [('tasks',task.pk),('requests',item.pk)]:
        status,payload=request(f'/api/internal/v1/{domain}/{pk}/comments/')
        check(f'{domain}_internal_comment_hidden_{index}',status==200 and 'SYNTHETIC_INTERNAL_MATRIX' not in json.dumps(payload))
    status,payload=request(f'/api/internal/v1/people/directory/{person.pk}/')
    check(f'directory_privacy_{index}',status==200 and payload.get('additional_email') is None)
    check(f'org_read_{index}',request(f'/api/internal/v1/org-units/{unit.pk}/')[0]==200)
    check(f'org_patch_denied_{index}',request(f'/api/internal/v1/org-units/{unit.pk}/','PATCH',{'name':'Forbidden'})[0]==403)
    status,payload=request(f'/api/internal/v1/tasks/{task.pk}/cancel/','POST',{'version':1,'reason':'Synthetic forbidden'})
    task.refresh_from_db()
    check(f'task_cancel_denied_{index}',status==400 and payload.get('error',{}).get('code')=='task_permission_denied' and task.status=='draft' and task.version==1)
person=subjects[0][0]
for label,path,method,data in [
    ('role_create','/api/internal/v1/roles/','POST',{'code':'forbidden','name':'Forbidden'}),
    ('role_patch',f'/api/internal/v1/roles/{role.pk}/','PATCH',{'name':'Forbidden'}),
    ('permission_grant','/api/internal/v1/role-permissions/','POST',{}),
    ('self_role_assignment',f'/api/internal/v1/employees/{director.pk}/roles/','POST',{'role':str(role.pk)}),
    ('other_account',f'/api/internal/v1/people/{person.pk}/access/restore/','POST',{}),
    ('invitation','/api/internal/v1/people/invitations/','POST',{'employee':str(person.pk)}),
    ('position_create','/api/internal/v1/positions/','POST',{'name':'Forbidden'}),
    ('employee_terminate',f'/api/internal/v1/employees/{person.pk}/terminate/','POST',{}),
    ('legacy_employee','/api/v1/employees/','GET',None),
]:
    check(label+'_denied',request(path,method,data)[0] in (403,404))
check('no_privilege_shortcuts',not user.is_staff and not user.is_superuser and not user.has_usable_password()
      and not user.user_permissions.exists() and not user.groups.exists() and not user.role_assignments.exists())
check('exact_allowlist',set(role.permission_grants.values_list('permission__code',flat=True))==set(ALLOWLIST))
print(json.dumps({'draft_allowlist':ALLOWLIST,'pass':sum(x['status']=='PASS' for x in results),'fail':sum(x['status']=='FAIL' for x in results),'synthetic_user_id':user.pk}))
if any(x['status']=='FAIL' for x in results):raise SystemExit(1)
