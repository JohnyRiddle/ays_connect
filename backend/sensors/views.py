from rest_framework import viewsets
from .models import Sensor
from .serializers import SensorDetailSerializer,SensorSerializer
class SensorViewSet(viewsets.ReadOnlyModelViewSet):
    def get_serializer_class(self):return SensorDetailSerializer if self.action=="retrieve" else SensorSerializer
    def get_queryset(self):
        u=self.request.user;qs=Sensor.objects.select_related("facility","zone").prefetch_related("readings","hourly_aggregates","events")
        if u.is_superuser:return qs
        facilities=list(u.role_assignments.values_list("facility_id",flat=True))
        if hasattr(u,"employee"):facilities+=list(u.employee.facilities.values_list("id",flat=True))
        return qs.filter(facility_id__in=facilities).distinct()
