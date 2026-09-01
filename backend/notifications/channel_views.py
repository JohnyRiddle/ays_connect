import secrets
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied,ValidationError
from audit.services import AuditService
from access_control.services import PermissionService
from .channels import TelegramBotClient
from .linking import TelegramLinkService
from .models import NotificationDelivery,NotificationPreference,NotificationQuietHours,TelegramAccount,TelegramWebhookEvent
from .serializers import DeliverySerializer,PreferenceSerializer,QuietHoursSerializer

def current_employee(request):
    employee=getattr(request.user,"employee",None)
    if not employee:raise ValidationError("Employee profile required")
    return employee
def masked_email(value):
    if not value or "@" not in value:return ""
    local,domain=value.split("@",1);return f"{local[:1]}***@{domain}"
class ChannelStatusView(APIView):
    def get(self,request):
        employee=current_employee(request);account=TelegramAccount.objects.filter(employee=employee,is_active=True).first();return Response({"in_app":{"available":True},"telegram":{"available":settings.NOTIFICATIONS_TELEGRAM_ENABLED,"linked":bool(account),"username":account.username if account else "","linked_at":account.linked_at if account else None},"email":{"available":bool(request.user.email),"address_masked":masked_email(request.user.email)}})
class TelegramStatusView(APIView):
    def get(self,request):
        account=TelegramAccount.objects.filter(employee=current_employee(request),is_active=True).first();return Response({"linked":bool(account),"username":account.username if account else "","linked_at":account.linked_at if account else None})
class TelegramLinkView(APIView):
    throttle_scope="binding"
    def post(self,request):
        raw,obj=TelegramLinkService.issue(current_employee(request),request.user);username=settings.TELEGRAM_BOT_USERNAME;return Response({"bot_username":username,"start_parameter":raw,"deep_link":f"https://t.me/{username}?start={raw}" if username else "","expires_at":obj.expires_at})
class TelegramUnlinkView(APIView):
    def post(self,request):return Response({"unlinked":TelegramLinkService.unlink(current_employee(request),request.user)})
class SelfPreferencesView(APIView):
    def get(self,request):return Response(PreferenceSerializer(NotificationPreference.objects.filter(employee=current_employee(request)),many=True).data)
    @transaction.atomic
    def put(self,request):
        employee=current_employee(request);reason=str(request.data.get("reason","*"));channel=str(request.data.get("channel",""));enabled=bool(request.data.get("enabled",True))
        if channel not in {"in_app","telegram","email"}:raise ValidationError("Invalid channel")
        if channel=="in_app" and reason=="SLA_ESCALATION" and not enabled:raise ValidationError({"code":"mandatory_channel"})
        obj,_=NotificationPreference.objects.update_or_create(employee=employee,reason=reason,channel=channel,defaults={"enabled":enabled});AuditService.record(action="notification.preference.updated",entity=obj,actor_user=request.user,actor_employee=employee,new_value={"reason":reason,"channel":channel,"enabled":enabled});return Response(PreferenceSerializer(obj).data)
class SelfQuietHoursView(APIView):
    def get_object(self,request):return NotificationQuietHours.objects.get_or_create(employee=current_employee(request),defaults={"starts_at":"22:00","ends_at":"08:00"})[0]
    def get(self,request):return Response(QuietHoursSerializer(self.get_object(request)).data)
    @transaction.atomic
    def put(self,request):
        obj=self.get_object(request);serializer=QuietHoursSerializer(obj,data=request.data);serializer.is_valid(raise_exception=True);serializer.save();AuditService.record(action="notification.quiet_hours.updated",entity=obj,actor_user=request.user,actor_employee=obj.employee,new_value=serializer.data);return Response(serializer.data)
class DeliveryDiagnosticsView(APIView):
    def get(self,request):
        employee=getattr(request.user,"employee",None)
        if not request.user.is_superuser and not PermissionService.has_permission(employee=employee,permission="notification.delivery.view"):raise PermissionDenied()
        qs=NotificationDelivery.objects.select_related("notification__recipient_employee").order_by("-created_at")
        for field in ("channel","status","last_error_code"):
            if request.query_params.get(field):qs=qs.filter(**{field:request.query_params[field]})
        if request.query_params.get("recipient"):qs=qs.filter(notification__recipient_employee_id=request.query_params["recipient"])
        return Response(DeliverySerializer(qs[:100],many=True).data)
class TelegramWebhookView(APIView):
    authentication_classes=[];permission_classes=[AllowAny]
    def post(self,request):
        expected=settings.TELEGRAM_WEBHOOK_SECRET;provided=request.headers.get("X-Telegram-Bot-Api-Secret-Token","")
        if not expected or not secrets.compare_digest(expected,provided):raise PermissionDenied("Invalid webhook secret")
        data=request.data
        if not isinstance(data,dict) or not isinstance(data.get("update_id"),int) or not isinstance(data.get("message"),dict):raise ValidationError("Invalid Telegram update")
        message=data["message"];sender=message.get("from") or {};chat=message.get("chat") or {};text=message.get("text","")
        if not isinstance(sender.get("id"),int) or not isinstance(chat.get("id"),int) or not isinstance(text,str):raise ValidationError("Invalid Telegram message")
        event,created=TelegramWebhookEvent.objects.get_or_create(update_id=data["update_id"],defaults={"telegram_user_id":sender["id"],"command":text.split(" ",1)[0][:32]})
        if not created:return Response({"ok":True,"duplicate":True})
        code="unsupported"
        try:
            if text.startswith("/start "):TelegramLinkService.consume(text.split(" ",1)[1].strip(),sender["id"],chat["id"],sender);code="linked";reply="AYS Connect подключён. Уведомления Telegram активированы."
            elif text=="/status":reply="AYS Connect подключён." if TelegramAccount.objects.filter(telegram_user_id=sender["id"],is_active=True).exists() else "Аккаунт не привязан.";code="status"
            elif text=="/unlink":
                account=TelegramAccount.objects.filter(telegram_user_id=sender["id"],is_active=True).select_related("employee").first();TelegramLinkService.unlink(account.employee) if account else None;reply="Telegram отключён.";code="unlinked"
            else:reply="Используйте ссылку из настроек AYS Connect." 
            if settings.TELEGRAM_BOT_TOKEN:TelegramBotClient().send_message(chat["id"],reply)
            event.status="processed"
        except Exception:event.status="failed";code="command_failed";raise
        finally:event.result_code=code;event.processed_at=timezone.now();event.save(update_fields=["status","result_code","processed_at"])
        return Response({"ok":True,"result":code})
