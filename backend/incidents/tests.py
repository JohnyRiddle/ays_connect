from datetime import date
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from accounts.models import User
from employees.models import Employee,EmployeeFacility
from incidents.models import Incident
from organizations.models import Cluster,Company,Department,Facility,Region
from sensors.models import Sensor
from sensors.services import ingest
class IncidentFlowTests(TestCase):
    def setUp(self):
        c=Company.objects.create(name="Т",short_name="Т");r=Region.objects.create(company=c,name="Р");cl=Cluster.objects.create(region=r,name="К");f=Facility.objects.create(cluster=cl,name="О",facility_type="restaurant",address="А");d=Department.objects.create(company=c,name="Тех")
        self.user=User.objects.create_user(username="worker",email="incident@test.local",password="pass12345");e=Employee.objects.create(user=self.user,company=c,department=d,employee_number="I1",position="Техник",hire_date=date.today());EmployeeFacility.objects.create(employee=e,facility=f)
        self.sensor=Sensor.objects.create(name="Камера",serial_number="INC-1",sensor_type="temperature",facility=f,unit="°C",allowed_min=0,allowed_max=6,critical_min=-5,critical_max=10,installed_at=date.today(),responsible=self.user)
        self.client=APIClient();self.client.force_authenticate(self.user)
    def test_full_incident_response(self):
        ingest(self.sensor,12);incident=Incident.objects.get();self.assertEqual(incident.status,Incident.Status.NOTIFIED)
        response=self.client.post(f"/api/v1/incidents/{incident.id}/acknowledge/");self.assertEqual(response.data["status"],Incident.Status.ACKNOWLEDGED);self.assertIsNotNone(response.data["response_run_id"])
        response=self.client.post(f"/api/v1/incidents/{incident.id}/escalate/",{"comment":"Нужна помощь"},format="json");self.assertEqual(response.data["status"],Incident.Status.ESCALATED);self.assertIsNotNone(response.data["task_id"])
        ingest(self.sensor,4);incident.refresh_from_db();self.assertEqual(incident.status,Incident.Status.NORMALIZED)
        response=self.client.post(f"/api/v1/incidents/{incident.id}/close/",{"reason":"Температура восстановлена"},format="json");self.assertEqual(response.data["status"],Incident.Status.CLOSED)
    def test_repeated_critical_reading_does_not_duplicate_incident(self):
        ingest(self.sensor,12);ingest(self.sensor,13);self.assertEqual(Incident.objects.count(),1)
