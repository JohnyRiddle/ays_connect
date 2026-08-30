from django.utils import timezone
from django.db import transaction
from rest_framework import mixins,status,viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied,ValidationError
from rest_framework.response import Response
from access_control.services import PermissionService
from audit.services import AuditService
from events.services import DomainEventService
from .models import Notification,NotificationDelivery,NotificationPreference,NotificationQuietHours,NotificationTemplate
from .serializers import DeliverySerializer,NotificationSerializer,PreferenceSerializer,QuietHoursSerializer,TemplateSerializer
from .services import render_template
def employee(r):return getattr(r.user,"employee",None)
def require(r,code):
    if not r.user.is_superuser and not PermissionService.has_permission(employee=employee(r),permission=code):raise PermissionDenied("Insufficient permissions.")
class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class=NotificationSerializer
    def get_queryset(self):
        qs=Notification.objects.filter(recipient=self.request.user);unread=self.request.query_params.get("unread")
        if unread in {"true","1"}:qs=qs.filter(is_read=False)
        if unread in {"false","0"}:qs=qs.filter(is_read=True)
        for f in ("notification_type","priority"):
            if self.request.query_params.get(f):qs=qs.filter(**{f:self.request.query_params[f]})
        return qs
    @action(detail=True,methods=["post"])
    def read(self,r,pk=None):
        x=self.get_object()
        if not x.is_read:x.is_read=True;x.read_at=timezone.now();x.save(update_fields=["is_read","read_at"])
        return Response(self.get_serializer(x).data)
    @action(detail=True,methods=["post"])
    def unread(self,r,pk=None):x=self.get_object();x.is_read=False;x.read_at=None;x.save(update_fields=["is_read","read_at"]);return Response(self.get_serializer(x).data)
    @action(detail=False,methods=["post"],url_path="read-all")
    def read_all(self,r):return Response({"status":"ok","updated":Notification.objects.filter(recipient=r.user,is_read=False).update(is_read=True,read_at=timezone.now())})
    @action(detail=False,methods=["get"],url_path="unread-count")
    def unread_count(self,r):return Response({"count":Notification.objects.filter(recipient=r.user,is_read=False).count()})
class TemplateViewSet(viewsets.ModelViewSet):
    queryset=NotificationTemplate.objects.all().order_by("code");serializer_class=TemplateSerializer
    def initial(self,r,*a,**kw):super().initial(r,*a,**kw);require(r,"notification.template.view" if r.method in {"GET","HEAD","OPTIONS"} else "notification.template.manage")
    @transaction.atomic
    def perform_create(self,s):x=s.save();AuditService.record(action="notification_template.created",entity=x,actor_user=self.request.user,actor_employee=employee(self.request),new_value=s.data);DomainEventService.publish(event_type="notification.template.created",entity=x,actor=self.request.user,payload={"code":x.code})
    @transaction.atomic
    def perform_update(self,s):old=TemplateSerializer(self.get_object()).data;x=s.save();AuditService.record(action="notification_template.updated",entity=x,actor_user=self.request.user,actor_employee=employee(self.request),old_value=old,new_value=s.data);DomainEventService.publish(event_type="notification.template.updated",entity=x,actor=self.request.user,payload={"code":x.code})
    @transaction.atomic
    def destroy(self,r,*a,**kw):x=self.get_object();x.is_active=False;x.save(update_fields=["is_active","updated_at"]);AuditService.record(action="notification_template.deactivated",entity=x,actor_user=r.user,actor_employee=employee(r));DomainEventService.publish(event_type="notification.template.deactivated",entity=x,actor=r.user,payload={"code":x.code});return Response(status=status.HTTP_204_NO_CONTENT)
    @action(detail=True,methods=["post"])
    def preview(self,r,pk=None):x=self.get_object();p=r.data.get("payload",{});return Response({"title":render_template(x.title_template,p,x.allowed_variables),"body":render_template(x.body_template,p,x.allowed_variables)})
class PreferenceViewSet(viewsets.ModelViewSet):
    serializer_class=PreferenceSerializer
    def get_queryset(self):return NotificationPreference.objects.filter(employee=employee(self.request))
    def perform_create(self,s):
        if not employee(self.request):raise ValidationError("Employee profile required")
        s.save(employee=employee(self.request))
class QuietHoursViewSet(viewsets.ViewSet):
    def retrieve(self,r,pk=None):
        if not employee(r):raise ValidationError("Employee profile required")
        x=NotificationQuietHours.objects.get_or_create(employee=employee(r),defaults={"starts_at":"22:00","ends_at":"08:00"})[0];return Response(QuietHoursSerializer(x).data)
    def update(self,r,pk=None):
        if not employee(r):raise ValidationError("Employee profile required")
        x=NotificationQuietHours.objects.get_or_create(employee=employee(r),defaults={"starts_at":"22:00","ends_at":"08:00"})[0];s=QuietHoursSerializer(x,data=r.data);s.is_valid(raise_exception=True);s.save();return Response(s.data)
class DeliveryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset=NotificationDelivery.objects.select_related("notification").all();serializer_class=DeliverySerializer
    def initial(self,r,*a,**kw):super().initial(r,*a,**kw);require(r,"notification.delivery.view")
