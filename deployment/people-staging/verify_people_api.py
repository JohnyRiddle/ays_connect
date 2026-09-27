"""Deployed local API acceptance; report only named assertions, never response payloads."""
import io
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.conf import settings
from accounts.serializers import EmailTokenSerializer
from employees.models import Employee, EmployeeProfile, EmployeeInvitation, OnboardingInstance, TeamMembership
from access_control.models import EmployeeRole
from PIL import Image

assert os.environ.get('PEOPLE_ACCEPTANCE_MODE') == '1'
assert settings.DATABASES['default']['HOST'] == 'db'
assert settings.DATABASES['default']['NAME'] == 'people_acceptance'
assert os.environ.get('DJANGO_SECRET_KEY'), 'Run through the staging runtime entrypoint'
run = sys.argv[1]
assert run.isalnum() and len(run) <= 12
fixture = json.loads((Path('/staging-private') / f'{run}.json').read_text())
actors = {name: Employee.objects.get(pk=item['employee']) for name,item in fixture['actors'].items()}

# This suite continues the desktop activation scenario on a fresh fixture.
# Refuse incomplete setup before any lifecycle mutations or token generation.
subject = actors['employee']
if (subject.user_id is None
    or not EmployeeProfile.objects.filter(employee=subject).exists()
    or EmployeeInvitation.objects.filter(employee=subject, used_at__isnull=False).count() != 1):
    print(json.dumps({'api_preflight': 'BLOCKED', 'code': 'BROWSER_ACTIVATION_REQUIRED'}))
    raise SystemExit(2)
tokens = {name:str(EmailTokenSerializer.get_token(employee.user).access_token) for name,employee in actors.items() if employee.user_id}
results = []
state = {}
P = '/api/internal/v1/people/'

def check(name, condition):
    row = {'check':name, 'status':'PASS' if condition else 'FAIL'}
    results.append(row)
    print(json.dumps(row), flush=True)

def api(name, path, method='GET', payload=None, raw=None, content_type=None):
    headers = {'Host':'localhost', 'Content-Type':content_type or 'application/json'}
    if name: headers['Authorization'] = 'Bearer ' + tokens[name]
    body = raw if raw is not None else (json.dumps(payload).encode() if payload is not None else None)
    req = urllib.request.Request('http://127.0.0.1:8000' + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            content = response.read()
            try: data = json.loads(content)
            except (ValueError, UnicodeDecodeError): data = content
            return response.status, data
    except urllib.error.HTTPError as error:
        return error.code, {}

def call(name, path, method='GET', payload=None, expected=200, label=None):
    status, data = api(name, path, method, payload)
    check(label or path.replace(str(actors['employee'].pk), '{employee}'), status == expected)
    if status != expected: raise AssertionError('HTTP_STATUS')
    return data

def A():
    e = actors['employee']
    check('A.unique_user_employee_profile', e.user_id is not None and Employee.objects.filter(user=e.user).count()==1 and EmployeeProfile.objects.filter(employee=e).count()==1)
    check('A.no_duplicate_employee_email', Employee.objects.filter(work_email=e.work_email).count()==1)
    check('A.one_used_invitation', EmployeeInvitation.objects.filter(employee=e, used_at__isnull=False).count()==1)

def B():
    data = call('employee', P+'me/', label='B.self_profile')
    data = call('employee', P+'me/', 'PATCH', {'version':data['version'], 'bio':'Private synthetic marker', 'additional_email':'private-synthetic@example.test', 'timezone':'Asia/Novosibirsk'}, label='B.profile_save')
    call('employee', P+'me/visibility/', 'PATCH', {'version':data['version'], 'bio_visibility':'private','additional_email_visibility':'private'}, label='B.visibility_save')
    for actor in ('manager','teammate','outside'):
        status, data = api(actor, P+f"directory/{actors['employee'].pk}/")
        check('B.privacy_'+actor, (status==404 if actor=='outside' else status==200 and data.get('bio') is None and data.get('additional_email') is None))
    status,_ = api('employee',P+'me/','PATCH',{'version':data.get('version',1),'is_active':False})
    check('B.corporate_patch_denied',status==400)
    image = io.BytesIO(); Image.new('RGB',(8,8),(24,64,128)).save(image,format='PNG')
    boundary = 'people-acceptance-boundary'
    def upload(content):
        raw=(f'--{boundary}\r\nContent-Disposition: form-data; name="avatar"; filename="synthetic.png"\r\nContent-Type: image/png\r\n\r\n'.encode()+content+f'\r\n--{boundary}--\r\n'.encode())
        return api('employee',P+'me/avatar/','POST',raw=raw,content_type=f'multipart/form-data; boundary={boundary}')[0]
    check('B.valid_avatar',upload(image.getvalue())==201)
    check('B.invalid_avatar',upload(b'<svg/>')==400)
    check('B.oversized_avatar',upload(b'x'*(5*1024*1024+1))==400)
    check('B.protected_avatar',api(None,P+'me/avatar/')[0]==401 and api('employee',P+'me/avatar/')[0]==200)
    check('B.outside_avatar',api('outside',P+f"directory/{actors['employee'].pk}/avatar/")[0]==404)
    progress=call('employee',P+'me/first-login/',label='B.first_login_resume')
    progress=call('employee',P+'me/first-login/','PATCH',{'version':progress['version'],'profile_completed':True},label='B.partial_first_login')
    progress=call('employee',P+'me/first-login/','PATCH',{'version':progress['version'],'timezone_completed':True,'visibility_completed':True},label='B.complete_first_login')
    check('B.first_login_saved',bool(progress['completed_at']))

def C():
    item=call('employee',P+'me/change-requests/','POST',{'field_type':'work_phone','requested_value':{'value':'+70000000001'},'reason':'Synthetic acceptance'},201,'C.submit')
    path=P+f"change-requests/{item['id']}/"
    check('C.outside_HR_IDOR_denied',api('outsidehr',path)[0] in (403,404))
    check('C.self_approval_denied',api('employee',path+'approve/','POST',{'version':item['version']})[0] in (400,403,404))
    reviewed=call('hr',path,label='C.scoped_sensitive_review')
    check('C.review_values_visible',reviewed['requested_value']=={'value':'+70000000001'})
    status,masked=api('coordinator',path)
    check('C.review_without_sensitive_masked',status==200 and masked['requested_value']=={'masked':True})
    item=call('hr',path+'approve/','POST',{'version':item['version']},label='C.approve')
    item=call('hr',path+'apply/','POST',{'version':item['version']},label='C.apply')
    check('C.apply_status',item['status']=='applied')
    repeated=call('hr',path+'apply/','POST',{'version':item['version']},label='C.repeat_apply')
    check('C.idempotence',repeated['version']==item['version'])
    state['change_request']=item['id']

def D():
    instance=call('coordinator',P+'onboarding/','POST',{'employee':str(actors['employee'].pk)},201,'D.assign_resolver')
    state['instance']=instance['id']
    check('D.duplicate_assignment_denied',api('coordinator',P+'onboarding/','POST',{'employee':str(actors['employee'].pk)})[0] in (400,409))
    instance=call('employee',P+f"me/onboarding/{instance['id']}/start/",'POST',{'version':instance['version']},label='D.start')
    steps={step['title_snapshot']:step for step in instance['steps']}
    manual=steps['Первый рабочий шаг']
    check('D.prerequisite_API_denied',api('employee',P+f"me/onboarding/{instance['id']}/steps/{manual['id']}/complete/",'POST',{'version':manual['version']})[0] in (400,409))
    for title in ('Профиль сотрудника','Первый рабочий шаг'):
        instance=call('employee',P+f"me/onboarding/{instance['id']}/",label='D.refresh_steps')
        step=next(x for x in instance['steps'] if x['title_snapshot']==title)
        call('employee',P+f"me/onboarding/{instance['id']}/steps/{step['id']}/complete/",'POST',{'version':step['version']},label='D.complete_'+title)
    instance=call('employee',P+f"me/onboarding/{instance['id']}/",label='D.progress')
    check('D.progress_not_inflated',instance['progress_percent']==66)
    state['work_step']=next(x for x in instance['steps'] if x['title_snapshot']=='Рабочая задача')['id']

def E():
    path=P+f"onboarding/{state['instance']}/steps/{state['work_step']}/create-task/"
    task=call('coordinator',path,'POST',{},label='E.create_task')
    again=call('coordinator',path,'POST',{},label='E.repeat_create_task')
    check('E.one_task',again['task_id']==task['task_id']); state['task']=task['task_id']
    path='/api/internal/v1/tasks/'+state['task']+'/'
    check('E.outside_task_denied',api('outside',path)[0] in (403,404))
    item=call('coordinator',path,label='E.task_draft')
    item=call('coordinator',path+'publish/','POST',{'version':item['version']},label='E.publish')
    item=call('employee',path+'start/','POST',{'version':item['version']},label='E.start')
    item=call('employee',path+'complete/','POST',{'version':item['version']},label='E.work_complete')
    check('E.waiting_acceptance',item['status']=='review')
    step=OnboardingInstance.objects.get(pk=state['instance']).steps.get(pk=state['work_step'])
    check('E.review_does_not_complete_step',api('employee',P+f"me/onboarding/{state['instance']}/steps/{step.pk}/complete/",'POST',{'version':step.version})[0] in (400,409))
    call('employee',path+'accept/','POST',{'version':item['version']},label='E.accept')
    for _ in range(10):
        step.refresh_from_db()
        if step.status=='completed':break
        time.sleep(1)
    check('E.worker_completes_TASK_step',step.status=='completed')

def G():
    path=P+f"{actors['employee'].pk}/access/"
    check('G.self_restore_denied',api('employee',path+'restore/','POST',{})[0] in (403,404))
    call('hr',path+'suspend/','POST',{},label='G.suspend')
    check('G.old_access_and_media_denied',api('employee',P+'me/')[0]==401 and api('employee',P+'me/avatar/')[0]==401)
    call('hr',path+'restore/','POST',{},label='G.restore')
    check('G.old_access_stays_denied',api('employee',P+'me/')[0]==401)
    actors['employee'].user.refresh_from_db();tokens['employee']=str(EmailTokenSerializer.get_token(actors['employee'].user).access_token)
    call('employee',P+'me/',label='G.fresh_access')

def H():
    e=actors['employee'];state['old_user']=e.user_id;state['old_number']=e.employee_number
    call('hr',P+f'employees/{e.pk}/terminate/','POST',{},label='H.terminate')
    check('H.old_access_denied',api('employee',P+'me/')[0]==401)
    check('H.team_memberships_closed',not TeamMembership.objects.filter(employee=e,valid_to__isnull=True).exists())
    check('H.old_permissions_closed',not EmployeeRole.objects.filter(employee=e,is_active=True).exists())
    check('H.profile_avatar_retained',EmployeeProfile.objects.filter(employee=e).exists() and bool(Employee.objects.get(pk=e.pk).avatar))
    call('hr',P+f'employees/{e.pk}/terminate/','POST',{},label='H.repeat_terminate')
    if state.get('task'):
        from work_tasks.models import Task
        check('H.work_task_retained',Task.objects.filter(pk=state['task']).exists())

def I():
    e=actors['employee']
    call('hr',P+f'employees/{e.pk}/reactivate/','POST',{},label='I.reactivate')
    invitation=call('hr',P+'invitations/','POST',{'employee':str(e.pk)},201,'I.invitation')
    password=fixture['actors']['employee']['password']
    call(None,'/api/public/v1/auth/invitations/accept/','POST',{'token':invitation['activation_token'],'password':password,'password_confirmation':password},label='I.activate_existing_account')
    check('I.old_access_stays_denied',api('employee',P+'me/')[0]==401)
    e.refresh_from_db()
    check('I.identity_preserved',e.user_id==state['old_user'] and e.employee_number==state['old_number'])
    check('I.no_old_roles_or_teams',not EmployeeRole.objects.filter(employee=e,is_active=True).exists() and not TeamMembership.objects.filter(employee=e,valid_to__isnull=True).exists())
    item=call('coordinator',P+'onboarding/','POST',{'employee':str(e.pk)},201,'I.new_onboarding')
    check('I.new_instance',item['id']!=state.get('instance'))

for name, action in [('A',A),('B',B),('C',C),('D',D),('E',E),('G',G),('H',H),('I',I)]:
    try: action()
    except Exception as exc:
        results.append({'check':name+'.dependent_steps','status':'BLOCKED','error_type':type(exc).__name__})
        print(json.dumps(results[-1]),flush=True)
report={'run':run,'checks':results,'state':state}
(Path('/staging-private')/f'{run}-api-report.json').write_text(json.dumps(report))
print(json.dumps({'api_pass':sum(x['status']=='PASS' for x in results),'api_fail':sum(x['status']=='FAIL' for x in results),'blocked':sum(x['status']=='BLOCKED' for x in results)}))
if any(x['status'] != 'PASS' for x in results):
    raise SystemExit(1)
