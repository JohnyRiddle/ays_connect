import hashlib
import secrets
from datetime import timedelta
from django.conf import settings
from django.db import IntegrityError,transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from audit.services import AuditService
from events.services import DomainEventService
from .models import NotificationDelivery,TelegramAccount,TelegramLinkToken

def token_hash(raw):return hashlib.sha256(raw.encode()).hexdigest()
class TelegramLinkService:
    @staticmethod
    @transaction.atomic
    def issue(employee,actor_user):
        now=timezone.now();TelegramLinkToken.objects.filter(employee=employee,used_at__isnull=True,revoked_at__isnull=True,expires_at__gt=now).update(revoked_at=now);raw=secrets.token_urlsafe(32);obj=TelegramLinkToken.objects.create(employee=employee,token_hash=token_hash(raw),expires_at=now+timedelta(seconds=settings.TELEGRAM_LINK_TOKEN_TTL));AuditService.record(action="notification.telegram.link_requested",entity=obj,actor_user=actor_user,actor_employee=employee);return raw,obj
    @staticmethod
    @transaction.atomic
    def consume(raw,user_id,chat_id,profile):
        now=timezone.now()
        try:obj=TelegramLinkToken.objects.select_for_update().select_related("employee").get(token_hash=token_hash(raw))
        except TelegramLinkToken.DoesNotExist:raise ValidationError({"code":"telegram_link_token_invalid"})
        if obj.used_at:raise ValidationError({"code":"telegram_link_token_used"})
        if obj.revoked_at or obj.expires_at<=now:raise ValidationError({"code":"telegram_link_token_expired"})
        conflict=TelegramAccount.objects.select_for_update().filter(telegram_user_id=user_id,is_active=True).exclude(employee=obj.employee).exists()
        if conflict:raise ValidationError({"code":"telegram_account_already_linked"})
        TelegramAccount.objects.select_for_update().filter(employee=obj.employee,is_active=True).update(is_active=False,unlinked_at=now)
        try:account=TelegramAccount.objects.create(employee=obj.employee,telegram_user_id=user_id,telegram_chat_id=chat_id,username=str(profile.get("username", ""))[:80],first_name=str(profile.get("first_name", ""))[:120],last_name=str(profile.get("last_name", ""))[:120],linked_at=now)
        except IntegrityError as exc:raise ValidationError({"code":"telegram_account_conflict"}) from exc
        obj.used_at=now;obj.save(update_fields=["used_at"]);NotificationDelivery.objects.filter(notification__recipient_employee=obj.employee,channel="telegram",status="suppressed",last_error_code="RECIPIENT_NOT_LINKED").update(status="pending",last_error_code="",next_attempt_at=None);AuditService.record(action="notification.telegram.linked",entity=account,actor_employee=obj.employee,new_value={"telegram_account_id":str(account.pk)});DomainEventService.publish(event_type="notification.channel.telegram_linked",entity=account,payload={"employee_id":str(obj.employee_id)});return account
    @staticmethod
    @transaction.atomic
    def unlink(employee,actor_user=None):
        now=timezone.now();account=TelegramAccount.objects.select_for_update().filter(employee=employee,is_active=True).first()
        if not account:return False
        account.is_active=False;account.unlinked_at=now;account.save(update_fields=["is_active","unlinked_at","updated_at"]);AuditService.record(action="notification.telegram.unlinked",entity=account,actor_user=actor_user,actor_employee=employee);DomainEventService.publish(event_type="notification.channel.telegram_unlinked",entity=account,actor=actor_user,payload={"employee_id":str(employee.pk)});return True
