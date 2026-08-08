from rest_framework import serializers
from .models import Sensor,SensorEvent,SensorHourlyAggregate,SensorReading
class ReadingSerializer(serializers.ModelSerializer):
    class Meta:model=SensorReading;fields=("value","level","recorded_at")
class AggregateSerializer(serializers.ModelSerializer):
    class Meta:model=SensorHourlyAggregate;fields=("hour","minimum","maximum","average","measurement_count","outside_norm_seconds","warning_count","critical_count")
class EventSerializer(serializers.ModelSerializer):
    class Meta:model=SensorEvent;fields=("id","level","started_at","ended_at","peak_value","task_id")
class SensorSerializer(serializers.ModelSerializer):
    type_label=serializers.CharField(source="get_sensor_type_display",read_only=True);state_label=serializers.CharField(source="get_state_display",read_only=True);facility_name=serializers.CharField(source="facility.name",read_only=True);zone_name=serializers.CharField(source="zone.name",read_only=True);latest=serializers.SerializerMethodField()
    class Meta:model=Sensor;fields=("id","name","serial_number","sensor_type","type_label","manufacturer","model","facility_name","zone_name","equipment","unit","allowed_min","allowed_max","critical_min","critical_max","battery_level","signal_quality","state","state_label","last_reading_at","latest")
    def get_latest(self,obj):
        r=obj.readings.first();return ReadingSerializer(r).data if r else None
class SensorDetailSerializer(SensorSerializer):
    readings=serializers.SerializerMethodField();hourly_aggregates=serializers.SerializerMethodField();events=EventSerializer(many=True,read_only=True)
    class Meta(SensorSerializer.Meta):fields=SensorSerializer.Meta.fields+("readings","hourly_aggregates","events")
    def get_readings(self,obj):return ReadingSerializer(obj.readings.all()[:288],many=True).data
    def get_hourly_aggregates(self,obj):return AggregateSerializer(obj.hourly_aggregates.all().order_by("-hour")[:168],many=True).data
