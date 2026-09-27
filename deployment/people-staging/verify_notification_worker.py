"""Synthetic worker-to-Mailpit smoke; no real recipients or printed mail bodies."""
import json, os, sys, time, uuid, urllib.request
sys.path.insert(0,'/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from accounts.models import User
from employees.models import Employee
from events.models import OutboxEvent
from notifications.models import NotificationIntent,Notification,NotificationDelivery
assert os.environ.get('PEOPLE_ACCEPTANCE_MODE')=='1'
assert settings.DATABASES['default']['NAME']=='people_acceptance' and settings.EMAIL_HOST=='mailpit'
assert settings.NOTIFICATIONS_EMAIL_ENABLED and not settings.NOTIFICATIONS_TELEGRAM_ENABLED
suffix=uuid.uuid4().hex[:10]
with transaction.atomic():
    u=User.objects.create_user(username='mail-'+suffix,email='mail-'+suffix+'@example.test',password=None)
    e=Employee.objects.create(user=u,first_name='Synthetic mail',employee_number='MAIL-'+suffix)
    source=OutboxEvent.objects.create(event_id=uuid.uuid4(),event_type='notification.requested',entity_type='EscalationExecution',entity_id=suffix,occurred_at=timezone.now(),payload={'reason':'SLA_ESCALATION','recipient_employee_id':str(e.pk),'request_id':suffix,'level':2,'event_type':'breach'})
for _ in range(15):
    if NotificationDelivery.objects.filter(notification__intent__source_event_id=source.event_id,status='delivered').count()==2:break
    time.sleep(1)
item=Notification.objects.filter(intent__source_event_id=source.event_id).first()
delivered=bool(item and set(item.deliveries.filter(status='delivered').values_list('channel',flat=True))=={'in_app','email'})
with urllib.request.urlopen('http://mailpit:8025/api/v1/messages',timeout=10) as response: inbox=json.load(response)
matches=[m for m in inbox.get('messages',[]) if suffix in m.get('Subject','')]
recipient_ok=len(matches)==1 and any(r.get('Address')==u.email for r in matches[0].get('To',[]))
print(json.dumps({'worker_delivered_both_channels':delivered,'mailpit_one_correct_recipient':recipient_ok,'logical_notifications':Notification.objects.filter(intent__source_event_id=source.event_id).count(),'source_event_id':str(source.event_id)}))
if not (delivered and recipient_ok):raise SystemExit(1)
