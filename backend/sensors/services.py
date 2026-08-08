from datetime import timedelta
from decimal import Decimal
from django.db.models import Avg,Count,Max,Min,Q
from django.utils import timezone
from .models import Sensor,SensorEvent,SensorHourlyAggregate,SensorReading
def level_for(sensor,value):
    value=Decimal(str(value))
    if value<sensor.critical_min or value>sensor.critical_max:return Sensor.State.CRITICAL
    if value<sensor.allowed_min or value>sensor.allowed_max:return Sensor.State.WARNING
    return Sensor.State.NORMAL
def ingest(sensor,value,recorded_at=None):
    recorded_at=recorded_at or timezone.now();level=level_for(sensor,value);reading=SensorReading.objects.create(sensor=sensor,value=value,level=level,recorded_at=recorded_at)
    sensor.state=level;sensor.last_reading_at=recorded_at;sensor.save(update_fields=["state","last_reading_at"])
    active=SensorEvent.objects.filter(sensor=sensor,ended_at__isnull=True).first()
    if level==Sensor.State.NORMAL and active:
        active.ended_at=recorded_at;active.save(update_fields=["ended_at"])
        from incidents.models import Incident,IncidentHistory
        incident=Incident.objects.filter(sensor_event=active).exclude(status__in=[Incident.Status.CLOSED,Incident.Status.FALSE_ALARM]).first()
        if incident:incident.status=Incident.Status.NORMALIZED;incident.normalized_at=recorded_at;incident.save(update_fields=["status","normalized_at"]);IncidentHistory.objects.create(incident=incident,action="normalized",details={"value":str(value)})
    elif level!=Sensor.State.NORMAL and not active:
        active=SensorEvent.objects.create(sensor=sensor,level=level,started_at=recorded_at,peak_value=value)
        if level==Sensor.State.CRITICAL:
            from incidents.models import Incident,IncidentHistory
            incident=Incident.objects.create(sensor=sensor,sensor_event=active,deviation_type=f"Выход за критический диапазон {sensor.unit}",level=level,started_at=recorded_at,peak_value=value,responsible=sensor.responsible,status=Incident.Status.NOTIFIED,notified_at=timezone.now(),is_demo=sensor.is_demo)
            IncidentHistory.objects.create(incident=incident,action="created",details={"value":str(value)})
    elif active and (active.peak_value is None or abs(Decimal(str(value)))>abs(active.peak_value)):active.peak_value=value;active.save(update_fields=["peak_value"])
    aggregate_hour=recorded_at.replace(minute=0,second=0,microsecond=0);qs=SensorReading.objects.filter(sensor=sensor,recorded_at__gte=aggregate_hour,recorded_at__lt=aggregate_hour+timedelta(hours=1));a=qs.aggregate(mi=Min("value"),ma=Max("value"),av=Avg("value"),count=Count("id"),warnings=Count("id",filter=Q(level=Sensor.State.WARNING)),critical=Count("id",filter=Q(level=Sensor.State.CRITICAL)))
    SensorHourlyAggregate.objects.update_or_create(sensor=sensor,hour=aggregate_hour,defaults={"minimum":a["mi"],"maximum":a["ma"],"average":a["av"],"measurement_count":a["count"],"warning_count":a["warnings"],"critical_count":a["critical"],"outside_norm_seconds":(a["warnings"]+a["critical"])*sensor.transmission_interval_seconds})
    return reading
