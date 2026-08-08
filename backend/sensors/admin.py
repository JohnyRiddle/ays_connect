from django.contrib import admin
from .models import Sensor,SensorEvent,SensorHourlyAggregate,SensorReading
for model in (Sensor,SensorReading,SensorHourlyAggregate,SensorEvent):admin.site.register(model)
