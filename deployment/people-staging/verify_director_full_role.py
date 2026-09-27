"""Explicit approved 95-code synthetic staging role. Never production or real credentials."""
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
from access_control.models import Permission, Role, RolePermission, EmployeeRole
from access_control.services import RoleService, PermissionService
from employees.models import Employee, EmployeeProfile
from organizations.models import OrgUnit
from work_tasks.models import Task, TaskComment
from service_requests.models import ServiceCategory, Service, RequestType, RequestTypeSchemaVersion, ServiceRequest, ServiceRequestComment

# Exact approved policy only; unknown/conditional/excluded grants are never assigned.
from access_control.operations_director_policy import load_policy
policy = load_policy()
ALLOWLIST = tuple(policy['allowlist'])
assert len(ALLOWLIST) == 95 and len(policy['excluded']) == 26 and len(policy['conditional']) == 30
assert not set(ALLOWLIST).intersection(policy['excluded'] + policy['conditional'])
assert os.environ.get('PEOPLE_ACCEPTANCE_MODE') == '1'
assert os.environ.get('DJANGO_SECRET_KEY')
assert settings.DATABASES['default']['NAME'] == 'people_acceptance'
assert settings.DATABASES['default']['HOST'] == 'db'
assert set(Permission.objects.values_list('code',flat=True)) == set(ALLOWLIST) | set(policy['excluded']) | set(policy['conditional'])
suffix='full'+uuid.uuid4().hex[:7]
with transaction.atomic():
    user=User.objects.create_user(username='matrix-'+suffix,email='matrix-'+suffix+'@example.test',password=None)
    director=Employee.objects.create(user=user,first_name='Synthetic director',employee_number='M-'+suffix)
    role=Role.objects.create(code='matrix-'+suffix,name='Synthetic approved 95-code business role')
    for code in ALLOWLIST:
        RolePermission.objects.create(role=role,permission=Permission.objects.get(code=code),scope='own' if code.endswith('_self') else 'global')
    assert user.pk != 2 and not user.is_staff and not user.is_superuser
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

def forbidden(label, path, method, data, expected=(403, 'permission_denied')):
    status, payload = request(path, method, data)
    code = payload.get('error', {}).get('code')
    check(label, (status, code) == expected)
    if (status, code) != expected:
        print(json.dumps({'diagnostic': label, 'http_status': status, 'error_code': code}))

def access_snapshot():
    # No secrets in output; compare the complete rows only in process memory.
    return {
        'roles': list(Role.objects.order_by('pk').values()),
        'grants': list(RolePermission.objects.order_by('pk').values()),
        'assignments': list(EmployeeRole.objects.filter(employee__in=[director, *[x[0] for x in subjects]]).order_by('pk').values()),
        'people': list(Employee.objects.filter(pk__in=[director.pk, *[x[0].pk for x in subjects]]).order_by('pk').values()),
        'account': list(User.objects.filter(pk=user.pk).values()),
        'units': list(OrgUnit.objects.filter(pk__in=[x[1].pk for x in subjects]).order_by('pk').values()),
    }
for index,(person,unit,task,item) in enumerate(subjects):
    check(f'task_cross_unit_{index}',request(f'/api/internal/v1/tasks/{task.pk}/')[0]==200)
    check(f'request_cross_unit_{index}',request(f'/api/internal/v1/requests/{item.pk}/')[0]==200)
    for domain,pk in [('tasks',task.pk),('requests',item.pk)]:
        status,payload=request(f'/api/internal/v1/{domain}/{pk}/comments/')
        check(f'{domain}_internal_comment_allowed_{index}',status==200 and 'SYNTHETIC_INTERNAL_MATRIX' in json.dumps(payload))
    status,payload=request(f'/api/internal/v1/people/directory/{person.pk}/')
    check(f'directory_privacy_{index}',status==200 and payload.get('additional_email') is None)
    check(f'org_read_{index}',request(f'/api/internal/v1/org-units/{unit.pk}/')[0]==200)
    before=access_snapshot()
    forbidden(f'org_patch_denied_{index}',f'/api/internal/v1/org-units/{unit.pk}/','PATCH',{'name':'Forbidden'})
    check(f'org_patch_preserves_data_{index}', before == access_snapshot())
    status,payload=request(f'/api/internal/v1/tasks/{task.pk}/cancel/','POST',{'version':1,'reason':'Synthetic forbidden'})
    task.refresh_from_db()
    check(f'task_cancel_allowed_{index}',status==200 and task.status=='cancelled' and task.version==2)
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
    before=access_snapshot()
    # AccountAccessView first filters by the action permission and then calls
    # get_object_or_404; the shared handler maps Django Http404 to request_failed.
    expected=(404,'request_failed') if label=='other_account' else (403,'permission_denied')
    forbidden(label+'_denied',path,method,data,expected=expected)
    check(label+'_preserves_access_data', before == access_snapshot())
check('no_privilege_shortcuts',not user.is_staff and not user.is_superuser and not user.has_usable_password()
      and not user.user_permissions.exists() and not user.groups.exists() and not user.role_assignments.exists())
check('exact_allowlist',set(role.permission_grants.values_list('permission__code',flat=True))==set(ALLOWLIST))
effective={code for code in Permission.objects.values_list('code',flat=True)
           if PermissionService.has_permission(employee=director,permission=code,obj=director)}
check('exact_effective_permissions_own_context', effective == set(ALLOWLIST))
check('single_active_role', list(EmployeeRole.objects.filter(employee=director,is_active=True).values_list('role_id',flat=True)) == [role.pk])
for code in policy['excluded'] + policy['conditional']:
    check('excluded_effective_'+code, not PermissionService.has_permission(employee=director,permission=code,obj=subjects[0][0]))
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from work_tasks.collaboration import CollaborationService
from service_requests.collaboration import RequestCollaborationService
from audit.models import AuditEvent
content=b'Synthetic attachment acceptance only.'
outside_user=User.objects.create_user(username='file-outsider-'+suffix,email='file-outsider-'+suffix+'@example.test',password=None)
Employee.objects.create(user=outside_user,employee_number='OUT-'+suffix)
outside_token=str(EmailTokenSerializer.get_token(outside_user).access_token)
def download(path,token):
    req=urllib.request.Request('http://127.0.0.1:8000'+path,headers={'Authorization':'Bearer '+token})
    try:
        with urllib.request.urlopen(req,timeout=10) as response:return response.status,response.read()==content
    except urllib.error.HTTPError as error:return error.code,False
task=subjects[0][2];item=subjects[0][3]
for domain,parent,attachment in [
    ('tasks',task,CollaborationService.add_attachment(task=task,actor=director,actor_user=user,
        uploaded_file=SimpleUploadedFile('synthetic.txt',content,content_type='text/plain'))),
    ('requests',item,RequestCollaborationService.add_attachment(request=item,actor=director,actor_user=user,visibility='internal',
        uploaded_file=SimpleUploadedFile('synthetic.txt',content,content_type='text/plain'))),
]:
    path=f'/api/internal/v1/{domain}/{parent.pk}/attachments/{attachment.pk}'
    check(domain+'_attachment_exact_download',download(path+'/download/',access)==(200,True))
    check(domain+'_attachment_outside_denied',download(path+'/download/',outside_token)[0] in (403,404))
    other=subjects[1][2 if domain=='tasks' else 3]
    check(domain+'_attachment_parent_IDOR_denied',download(path.replace(str(parent.pk),str(other.pk))+'/download/',access)[0]==404)
    forbidden(domain+'_attachment_delete_denied',path+'/','DELETE',None,
              expected=(400, 'task_permission_denied' if domain=='tasks' else 'request_permission_denied'))
    attachment.refresh_from_db();check(domain+'_delete_denial_preserves_file',attachment.deleted_at is None)
    check(domain+'_attachment_audit_actor',AuditEvent.objects.filter(entity_id=str(attachment.pk),actor=user,actor_employee=director).exists())
    # Only this run's synthetic attachment: soft-delete metadata, retain physical file.
    type(attachment).objects.filter(pk=attachment.pk).update(deleted_at=timezone.now())
    check(domain+'_deleted_download_denied',download(path+'/download/',access)[0]==404)
def operation(label, path, method='GET', data=None, expected=200):
    status, payload=request('/api/internal/v1/'+path,method,data)
    check(label,status==expected)
    if status!=expected:
        print(json.dumps({'diagnostic':label,'http_status':status,'error_code':payload.get('error',{}).get('code')}))
        raise AssertionError('Synthetic operation failed')
    return payload

from employees.models import AssignmentTarget
from datetime import timedelta
target=AssignmentTarget.objects.create(target_type='employee',employee=director)
for index,(person,unit,_,_) in enumerate(subjects):
    try:
        tag=f'business_{index}_'
        task=operation(tag+'task_create','tasks/','POST',{'title':'Synthetic lifecycle','org_unit':str(unit.pk),
            'responsible_target':str(target.pk),'executor_target':str(target.pk),'acceptance_policy':'author'},201)
        path=f"tasks/{task['id']}/"
        task=operation(tag+'task_edit',path,'PATCH',{'version':task['version'],'title':'Synthetic edited'})
        for action in ('publish','start','complete'):
            task=operation(tag+action,path+action+'/','POST',{'version':task['version']})
        check(tag+'mandatory_review',task['status']=='review')
        task=operation(tag+'reject',path+'reject/','POST',{'version':task['version'],'reason':'Synthetic review'})
        task=operation(tag+'complete_again',path+'complete/','POST',{'version':task['version']})
        task=operation(tag+'accept',path+'accept/','POST',{'version':task['version']})
        check(tag+'completed',task['status']=='completed')
        task=operation(tag+'reopen',path+'reopen/','POST',{'version':task['version'],'reason':'Synthetic return'})
        operation(tag+'internal_comment',path+'comments/','POST',{'body':'Synthetic internal','is_internal':True},201)
        check(tag+'work_audit_actor',AuditEvent.objects.filter(entity_id=task['id'],actor=user,actor_employee=director).exists())
        template=operation(tag+'template_create','task-templates/','POST',{'name':'Synthetic '+tag,
            'task_title':'Synthetic recurrence','org_unit':str(unit.pk),'responsible_target':str(target.pk)},201)
        operation(tag+'template_use',f"task-templates/{template['id']}/create-task/",'POST',{'create_and_publish':True},201)
        recurrence=operation(tag+'recurrence_create','task-recurrences/','POST',{'name':'Synthetic '+tag,
            'task_template':template['id'],'rrule':'FREQ=DAILY;COUNT=2','timezone':'UTC',
            'starts_at':(timezone.now()+timedelta(days=1)).isoformat()},201)
        operation(tag+'recurrence_pause',f"task-recurrences/{recurrence['id']}/pause/",'POST',{})
        onboarding=operation(tag+'onboarding_template','people/onboarding-templates/','POST',
            {'name':'Synthetic '+tag,'scope':'org_unit','org_unit':str(unit.pk)},201)
        operation(tag+'onboarding_publish',f"people/onboarding-templates/{onboarding['id']}/publish/",'POST',
            {'version':onboarding['version'],'steps':[{'key':'manual','title':'Synthetic manual','step_type':'manual'}]})
        instance=operation(tag+'onboarding_assign','people/onboarding/','POST',
            {'employee':str(person.pk),'template':onboarding['id']},201)
        instance=operation(tag+'onboarding_start',f"people/onboarding/{instance['id']}/start/",'POST',{'version':instance['version']})
        step=instance['steps'][0]
        operation(tag+'onboarding_skip',f"people/onboarding/{instance['id']}/steps/{step['id']}/skip/",'POST',
            {'version':step['version'],'reason':'Synthetic acceptance'})
        operation(tag+'management_metrics',f'performance/org-units/{unit.pk}/summary/')
    except AssertionError:
        continue
try:
    calendar=operation('sla_calendar_create','sla/calendars/','POST',
        {'name':'Synthetic matrix','code':suffix,'timezone':'UTC'},201)
    operation('sla_interval','sla/calendars/'+calendar['id']+'/working-intervals/','POST',
        {'weekday':0,'start_time':'09:00','end_time':'18:00'},201)
    operation('sla_calendar_publish','sla/calendars/'+calendar['id']+'/publish/','POST',{},201)
    policy_row=operation('sla_policy_create','sla/policies/','POST',{'name':'Synthetic matrix','code':suffix,
        'draft_time_mode':'elapsed_time','draft_response_duration_seconds':3600,'draft_resolution_duration_seconds':7200},201)
    operation('sla_policy_publish','sla/policies/'+policy_row['id']+'/publish/','POST',{},201)
    operation('sla_assignment_rule','sla/assignment-rules/','POST',
        {'policy':policy_row['id'],'org_unit':str(subjects[0][1].pk)},201)
    check('sla_does_not_mutate_rbac',set(role.permission_grants.values_list('permission__code',flat=True))==set(ALLOWLIST))
except AssertionError:
    pass
print(json.dumps({'approved_allowlist_count':len(ALLOWLIST),'pass':sum(x['status']=='PASS' for x in results),'fail':sum(x['status']=='FAIL' for x in results),'synthetic_user_id':user.pk}))
if any(x['status']=='FAIL' for x in results):raise SystemExit(1)
