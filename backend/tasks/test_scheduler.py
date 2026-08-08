from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from checklists.models import ChecklistRun, ChecklistTemplate
from organizations.models import Cluster, Company, Facility, Region
from tasks.models import RecurrenceRule, Task
from tasks.scheduler import run_due_schedules


class SchedulerTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user(username="scheduler",email="scheduler@test.local",password="pass12345")
        company=Company.objects.create(name="Компания",short_name="К")
        region=Region.objects.create(company=company,name="Регион")
        cluster=Cluster.objects.create(region=region,name="Кластер")
        self.facility=Facility.objects.create(cluster=cluster,name="Объект",facility_type=Facility.Type.OFFICE,address="Адрес",manager=self.user)

    def test_recurring_task_is_generated_once_and_next_run_advances(self):
        now=timezone.now(); deadline=now+timedelta(hours=2)
        template=Task.objects.create(title="Регламент",creator=self.user,assignee=self.user,facility=self.facility,initial_deadline=deadline,deadline=deadline,status=Task.Status.DRAFT)
        rule=RecurrenceRule.objects.create(task_template=template,frequency=RecurrenceRule.Frequency.DAILY,next_run_at=now-timedelta(minutes=1))
        first=run_due_schedules(now); second=run_due_schedules(now)
        self.assertEqual(first["tasks"],1); self.assertEqual(second["tasks"],0)
        self.assertEqual(Task.objects.filter(recurrence_rule=rule).count(),1)
        rule.refresh_from_db(); self.assertGreater(rule.next_run_at,now)

    def test_one_time_checklist_is_generated_and_deactivated(self):
        now=timezone.now()
        template=ChecklistTemplate.objects.create(name="Разовая проверка",category="Контроль",facility=self.facility,frequency=ChecklistTemplate.Frequency.ONCE,default_assignee=self.user,next_run_at=now-timedelta(minutes=1))
        result=run_due_schedules(now)
        self.assertEqual(result["checklists"],1)
        self.assertEqual(ChecklistRun.objects.filter(template=template).count(),1)
        template.refresh_from_db(); self.assertFalse(template.is_active); self.assertIsNone(template.next_run_at)
