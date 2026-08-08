from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Notification
from .serializers import NotificationSerializer
class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class=NotificationSerializer
    def get_queryset(self):return Notification.objects.filter(recipient=self.request.user)
    @action(detail=True,methods=["post"])
    def read(self,request,pk=None):
        item=self.get_object();item.is_read=True;item.read_at=timezone.now();item.save(update_fields=["is_read","read_at"]);return Response(NotificationSerializer(item).data)
    @action(detail=False,methods=["post"],url_path="read-all")
    def read_all(self,request):
        Notification.objects.filter(recipient=request.user,is_read=False).update(is_read=True,read_at=timezone.now());return Response({"status":"ok"})
