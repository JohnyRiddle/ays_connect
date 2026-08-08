from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from accounts.models import User
from checklists.models import ChecklistQuestion,ChecklistRun,ChecklistTemplate,Violation
from organizations.models import Cluster,Company,Facility,Region
from tasks.models import Task

class ChecklistFlowTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user(username="worker",email="worker@check.test",password="pass12345")
        company=Company.objects.create(name="Тест",short_name="Т");region=Region.objects.create(company=company,name="Регион");cluster=Cluster.objects.create(region=region,name="Город")
        facility=Facility.objects.create(cluster=cluster,name="Объект",facility_type=Facility.Type.RESTAURANT,address="Адрес")
        template=ChecklistTemplate.objects.create(name="Контроль",category="ХАССП",facility=facility,is_haccp=True)
        self.q1=ChecklistQuestion.objects.create(template=template,text="Чистота",question_type=ChecklistQuestion.Type.BOOLEAN,order=1)
        self.q2=ChecklistQuestion.objects.create(template=template,text="Температура",question_type=ChecklistQuestion.Type.TEMPERATURE,order=2,min_value=0,max_value=6)
        self.run=ChecklistRun.objects.create(template=template,assignee=self.user,facility=facility,due_at=timezone.now()+timedelta(hours=1))
        self.client=APIClient();self.client.force_authenticate(self.user)
    def test_required_answers_cannot_be_skipped(self):
        response=self.client.post(f"/api/v1/checklists/runs/{self.run.id}/complete/",{"answers":[{"question":self.q1.id,"value":True}]},format="json")
        self.assertEqual(response.status_code,400)
    def test_violation_creates_corrective_task(self):
        response=self.client.post(f"/api/v1/checklists/runs/{self.run.id}/complete/",{"answers":[{"question":self.q1.id,"value":False,"comment":"Требуется уборка"},{"question":self.q2.id,"value":4}]},format="json")
        self.assertEqual(response.status_code,200);self.assertEqual(response.data["status"],ChecklistRun.Status.VIOLATION)
        self.assertEqual(Violation.objects.count(),1);self.assertEqual(Task.objects.filter(source=Task.Source.CHECKLIST).count(),1)
