"""Synthetic People reasons through live worker and internal Mailpit; no real mail."""
import os,sys,json,time,uuid,urllib.request
sys.path.insert(0,'/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from django.conf import settings
from django.utils import timezone
from accounts.models import User
from employees.models import Employee
from access_control.models import EmployeeRole,Permission,Role,RolePermission
from events.models import OutboxEvent
from notifications.models import Notification,NotificationDelivery
from work_tasks.models import Task
assert os.environ.get('PEOPLE_ACCEPTANCE_MODE')=='1'
assert settings.DATABASES['default']['NAME']=='people_acceptance' and settings.DATABASES['default']['HOST']=='db'
assert settings.EMAIL_HOST=='mailpit' and settings.NOTIFICATIONS_EMAIL_ENABLED and not settings.NOTIFICATIONS_TELEGRAM_ENABLED
suffix=uuid.uuid4().hex[:10]
user=User.objects.create_user(username='people-mail-'+suffix,email='people-mail-'+suffix+'@example.test',password=None)
assert user.pk!=2
employee=Employee.objects.create(user=user,employee_number='PM-'+suffix)
permission,_=Permission.objects.get_or_create(code='task.view',defaults={'name':'View Work tasks'})
role=Role.objects.create(code='people-mail-'+suffix,name='Synthetic notification task reader')
RolePermission.objects.create(role=role,permission=permission,scope='own')
EmployeeRole.objects.create(employee=employee,role=role)
task=Task.objects.create(number='TASK-MAIL-'+suffix,title='Synthetic notification Work task',author=employee,
    executor_employee=employee,created_by=user,updated_by=user)
sources=[]
for reason in ['WORK_TASK_REOPENED','WORK_TASK_REJECTED','PEOPLE_INVITATION_EXPIRED','PEOPLE_STEP_OVERDUE','PEOPLE_ONBOARDING_REOPEN_BLOCKED']:
    sources.append(OutboxEvent.objects.create(event_id=uuid.uuid4(),event_type='notification.requested',entity_type='SyntheticPeople',entity_id=suffix,
        occurred_at=timezone.now(),payload={'reason':reason,'recipient_employee_id':str(employee.pk),'task_id':str(task.pk),
        'task_number':task.number,'actor_name':'Synthetic actor','reason_text':'Synthetic return',
        'invitation_id':str(uuid.uuid4()),'onboarding_id':str(uuid.uuid4()),'step_title':'Synthetic step '+suffix}))
ids=[s.event_id for s in sources]
for _ in range(30):
    if NotificationDelivery.objects.filter(notification__intent__source_event_id__in=ids,status='delivered').count()==10:break
    time.sleep(1)
checks=[]
for source in sources:
    rows=Notification.objects.filter(intent__source_event_id=source.event_id)
    item=rows.first()
    ok=rows.count()==1 and item.recipient_id==user.pk
    ok=ok and set(item.deliveries.filter(status='delivered').values_list('channel',flat=True))=={'in_app','email'}
    ok=ok and all(d.attempt_log.count()==1 for d in item.deliveries.all())
    checks.append({'reason':source.payload['reason'],'exact_logical_and_channel_delivery':bool(ok)})
with urllib.request.urlopen('http://mailpit:8025/api/v1/messages',timeout=10) as response:inbox=json.load(response)
messages=[m for m in inbox.get('messages',[]) if any(r.get('Address')==user.email for r in m.get('To',[]))]
mail_ok=len(messages)==5 and len({m['Subject'] for m in messages})==5
print(json.dumps({'checks':checks,'mailpit_five_distinct_messages_to_synthetic_recipient':mail_ok}))
if not(mail_ok and all(c['exact_logical_and_channel_delivery'] for c in checks)):raise SystemExit(1)
