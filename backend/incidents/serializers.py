from rest_framework import serializers
from .models import Incident,IncidentHistory
class HistorySerializer(serializers.ModelSerializer):
    actor_name=serializers.CharField(source="actor.get_full_name",read_only=True)
    class Meta:model=IncidentHistory;fields=("id","actor_name","action","details","created_at")
class IncidentSerializer(serializers.ModelSerializer):
    sensor_name=serializers.CharField(source="sensor.name",read_only=True);facility_name=serializers.CharField(source="sensor.facility.name",read_only=True);zone_name=serializers.CharField(source="sensor.zone.name",read_only=True);unit=serializers.CharField(source="sensor.unit",read_only=True);status_label=serializers.CharField(source="get_status_display",read_only=True);responsible_name=serializers.CharField(source="responsible.get_full_name",read_only=True);response_seconds=serializers.IntegerField(read_only=True);history=HistorySerializer(many=True,read_only=True)
    class Meta:model=Incident;fields=("id","sensor","sensor_name","facility_name","zone_name","unit","deviation_type","level","started_at","detected_at","peak_value","responsible_name","notified_at","acknowledged_at","normalized_at","closed_at","reason","comment","status","status_label","response_seconds","response_run_id","task_id","history")
