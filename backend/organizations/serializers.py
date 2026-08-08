from rest_framework import serializers
from .models import Cluster, Company, Department, Facility, Region, Zone

class ZoneSerializer(serializers.ModelSerializer):
    class Meta: model = Zone; fields = ("id", "name", "description")
class FacilitySerializer(serializers.ModelSerializer):
    type_label = serializers.CharField(source="get_facility_type_display", read_only=True)
    zones = ZoneSerializer(many=True, read_only=True)
    class Meta: model = Facility; fields = ("id", "name", "facility_type", "type_label", "address", "work_schedule", "status", "zones")
class ClusterSerializer(serializers.ModelSerializer):
    facilities = FacilitySerializer(many=True, read_only=True)
    class Meta: model = Cluster; fields = ("id", "name", "facilities")
class RegionSerializer(serializers.ModelSerializer):
    clusters = ClusterSerializer(many=True, read_only=True)
    class Meta: model = Region; fields = ("id", "name", "timezone", "clusters")
class DepartmentSerializer(serializers.ModelSerializer):
    class Meta: model = Department; fields = ("id", "name", "parent_id")
class CompanySerializer(serializers.ModelSerializer):
    regions = RegionSerializer(many=True, read_only=True)
    departments = DepartmentSerializer(many=True, read_only=True)
    class Meta: model = Company; fields = ("id", "name", "short_name", "description", "status", "timezone", "regions", "departments")
