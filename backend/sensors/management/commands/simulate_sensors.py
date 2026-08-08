import random
from django.core.management.base import BaseCommand
from sensors.models import Sensor
from sensors.services import ingest
class Command(BaseCommand):
    help="Добавляет по одному демонстрационному показанию"
    def handle(self,*args,**kwargs):
        for sensor in Sensor.objects.filter(is_demo=True):
            center=float(sensor.allowed_min+sensor.allowed_max)/2;ingest(sensor,round(center+random.uniform(-1.5,1.5),2))
        self.stdout.write(self.style.SUCCESS("Показания добавлены"))
