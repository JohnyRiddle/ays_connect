"""Live isolated milestone worker → Outbox → Notification Core → Mailpit gate."""
import json
import os
import sys
import time
import uuid
from urllib.request import urlopen
sys.path.insert(0,"/app")
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
import django
django.setup()
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from access_control.models import EmployeeRole, Permission, Role, RolePermission
from employees.models import Employee
from projects.models import ProjectMilestoneDueNotice
from projects.services import ProjectService
from projects.management.commands.process_milestone_due import process_due_milestones
from events.models import OutboxEvent
from notifications.models import Notification, NotificationDelivery

assert os.environ.get("PEOPLE_ACCEPTANCE_MODE")=="1"
assert settings.DATABASES["default"]["NAME"]=="projects_acceptance" and settings.DATABASES["default"]["HOST"]=="db"
assert settings.EMAIL_HOST=="mailpit" and settings.NOTIFICATIONS_EMAIL_ENABLED and not settings.NOTIFICATIONS_TELEGRAM_ENABLED
fixture=json.loads(open("/staging-private/projects-fixture.json",encoding="utf8").read())
manager=Employee.objects.select_related("user").get(pk=fixture["actors"]["manager"]["employee"])
suffix=uuid.uuid4().hex[:10]
user=get_user_model().objects.create_user(username="synthetic-project-due-"+suffix,email="project-due-"+suffix+"@example.test",password=None)
recipient=Employee.objects.create(user=user,first_name="Synthetic due recipient")
role=Role.objects.create(code="synthetic-project-due-"+suffix,name="Synthetic project due reader")
RolePermission.objects.create(role=role,permission=Permission.objects.get(code="project.view"),scope="global")
EmployeeRole.objects.create(employee=recipient,role=role)
project=ProjectService.create(actor=manager,actor_user=manager.user,name="Synthetic due notification",manager=manager)
milestone=ProjectService.create_milestone(project=project,actor=manager,actor_user=manager.user,version=project.version,
    name="Synthetic due gate",due_at=timezone.now()-timedelta(minutes=1),responsible=recipient)
for _ in range(35):
    notices=ProjectMilestoneDueNotice.objects.filter(milestone=milestone).count()
    deliveries=NotificationDelivery.objects.filter(notification__recipient=user,
        notification__intent__reason="PROJECT_MILESTONE_DUE",status="delivered").count()
    if notices==1 and deliveries==2: break
    time.sleep(1)
assert notices==1 and deliveries==2,"Workers did not deliver exactly one in-app/email pair in 35 seconds"
assert process_due_milestones()==0,"Repeated due scan emitted a second notice"
assert ProjectMilestoneDueNotice.objects.filter(milestone=milestone).count()==1
assert OutboxEvent.objects.filter(event_type="notification.requested",payload__reason="PROJECT_MILESTONE_DUE",
    payload__milestone_id=str(milestone.pk)).count()==1
item=Notification.objects.get(recipient=user,intent__reason="PROJECT_MILESTONE_DUE")
assert set(item.deliveries.values_list("channel",flat=True))=={"in_app","email"}
assert all(d.attempt_log.count()==1 for d in item.deliveries.all())
with urlopen("http://mailpit:8025/api/v1/messages",timeout=8) as response:
    inbox=json.load(response)
messages=[m for m in inbox.get("messages",[]) if any(r.get("Address")==user.email for r in m.get("To",[]))]
due_messages=[m for m in messages if m["Subject"]=="Наступил срок контрольной точки"]
assert len(due_messages)==1
print("projects_notification_worker=PASS due_notice=1 outbox=1 notification=1 in_app_email=2 mailpit_synthetic_due=1 repeated_scan=0")
