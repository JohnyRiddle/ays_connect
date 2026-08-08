from datetime import date
from django.test import TestCase
from django.utils import timezone
from accounts.models import User
from organizations.models import Cluster,Company,Facility,Region
from sensors.models import Sensor,SensorEvent,SensorHourlyAggregate
from sensors.services import ingest
class SensorAnalysisTests(TestCase):
    def setUp(self):
        c=Company.objects.create(name="Т",short_name="Т");r=Region.objects.create(company=c,name="Р");cl=Cluster.objects.create(region=r,name="К");f=Facility.objects.create(cluster=cl,name="О",facility_type="restaurant",address="А")
        self.sensor=Sensor.objects.create(name="Температура",serial_number="T1",sensor_type="temperature",facility=f,unit="°C",allowed_min=0,allowed_max=6,critical_min=-5,critical_max=10,installed_at=date.today())
    def test_normal_and_critical_readings_are_classified(self):
        self.assertEqual(ingest(self.sensor,4).level,Sensor.State.NORMAL)
        self.assertEqual(ingest(self.sensor,12).level,Sensor.State.CRITICAL)
        self.assertEqual(SensorEvent.objects.filter(ended_at__isnull=True).count(),1)
    def test_hourly_aggregate_keeps_all_measurements(self):
        now=timezone.now();ingest(self.sensor,2,now);ingest(self.sensor,4,now)
        aggregate=SensorHourlyAggregate.objects.get(sensor=self.sensor,hour=now.replace(minute=0,second=0,microsecond=0))
        self.assertEqual(aggregate.measurement_count,2);self.assertEqual(float(aggregate.average),3)
