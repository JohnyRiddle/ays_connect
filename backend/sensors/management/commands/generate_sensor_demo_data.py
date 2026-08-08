import math,random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from sensors.models import Sensor
from sensors.services import ingest
class Command(BaseCommand):
    help="Генерирует 7 дней демонстрационных показаний"
    def handle(self,*args,**kwargs):
        for sensor in Sensor.objects.filter(is_demo=True):
            if sensor.readings.exists():continue
            start=timezone.now()-timedelta(days=7)
            for i in range(7*24*4):
                base=float(sensor.allowed_min+sensor.allowed_max)/2;value=base+math.sin(i/12)*1.2+random.uniform(-.35,.35)
                if 400<i<408:value=float(sensor.critical_max)+2.5
                ingest(sensor,round(value,2),start+timedelta(minutes=15*i))
        self.stdout.write(self.style.SUCCESS("Демонстрационные показания созданы"))
