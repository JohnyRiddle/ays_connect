from datetime import datetime,time,timedelta,timezone as dt_timezone
import uuid
from unittest.mock import patch
from unittest import skipUnless
from concurrent.futures import ThreadPoolExecutor
from django.core import mail
from django.db import IntegrityError,transaction,connection,connections,close_old_connections
from django.test import TestCase,TransactionTestCase,override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from accounts.models import User
from employees.models import Employee
from .channels import DjangoEmailProvider,EmailChannelHandler,ProviderFailure,ProviderResult,TelegramChannelHandler
from .linking import TelegramLinkService
from .models import Notification,NotificationDelivery,NotificationIntent,NotificationPreference,NotificationQuietHours,TelegramAccount,TelegramLinkToken,TelegramWebhookEvent
from .services import NotificationChannelRouter,deliver_one,quiet_hours_end,reconcile_deliveries
from audit.models import AuditEvent

def employee(s="x",email=None):
    user=User.objects.create_user(username=f"ext{s}",email=email if email is not None else f"person{s}@example.com",password="pass12345");return user,Employee.objects.create(user=user,employee_number=f"EXT-{s}")
def notification(emp,priority="critical",reason="SLA_ESCALATION"):
    intent=NotificationIntent.objects.create(source_event_id=uuid.uuid4(),event_type="notification.requested",reason=reason,payload={})
    return Notification.objects.create(recipient=emp.user,recipient_employee=emp,intent=intent,notification_type="sla_escalation",priority=priority,title="Alert",message="Body")
class FakeTelegram:
    def send_message(self,chat_id,text):return ProviderResult("77",{"provider_date":1})
class FailureHandler:
    def __init__(self,failure):self.failure=failure
    def send(self,delivery):raise self.failure

class TelegramLinkingTests(TestCase):
    @override_settings(TELEGRAM_BOT_USERNAME="ays_test_bot")
    def test_link_token_is_hashed_and_webhook_links_once(self):
        user,emp=employee();client=APIClient();client.force_authenticate(user);response=client.post("/api/internal/v1/notification-channels/telegram/link/");raw=response.data["start_parameter"]
        self.assertNotEqual(TelegramLinkToken.objects.get().token_hash,raw);client.force_authenticate(user=None)
        with override_settings(TELEGRAM_WEBHOOK_SECRET="secret"):
            payload={"update_id":1,"message":{"text":f"/start {raw}","from":{"id":123,"username":"person"},"chat":{"id":456}}};headers={"HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN":"secret"}
            self.assertEqual(client.post("/api/integrations/telegram/webhook/",payload,format="json",**headers).status_code,200);self.assertTrue(TelegramAccount.objects.filter(employee=emp,telegram_user_id=123,is_active=True).exists())
            self.assertTrue(client.post("/api/integrations/telegram/webhook/",payload,format="json",**headers).data["duplicate"]);self.assertEqual(TelegramWebhookEvent.objects.count(),1)
    @override_settings(TELEGRAM_WEBHOOK_SECRET="secret")
    def test_webhook_rejects_missing_secret(self):
        client=APIClient();self.assertEqual(client.post("/api/integrations/telegram/webhook/",{},format="json").status_code,403)
    def test_expired_reused_conflict_relink_and_unlink(self):
        u,a=employee("a");_,b=employee("b");raw,obj=TelegramLinkService.issue(a,u);obj.expires_at=timezone.now()-timedelta(seconds=1);obj.save()
        with self.assertRaises(Exception):TelegramLinkService.consume(raw,1,1,{})
        raw,_=TelegramLinkService.issue(a,u);first=TelegramLinkService.consume(raw,1,1,{})
        with self.assertRaises(Exception):TelegramLinkService.consume(raw,1,1,{})
        raw,_=TelegramLinkService.issue(b,b.user)
        with self.assertRaises(Exception):TelegramLinkService.consume(raw,1,1,{})
        raw,_=TelegramLinkService.issue(a,u);second=TelegramLinkService.consume(raw,2,2,{});first.refresh_from_db();self.assertFalse(first.is_active);self.assertTrue(second.is_active);self.assertTrue(TelegramLinkService.unlink(a,u));self.assertFalse(TelegramAccount.objects.filter(employee=a,is_active=True).exists())
    def test_link_audit_outbox_failure_rolls_back(self):
        user,emp=employee("rollback");raw,token=TelegramLinkService.issue(emp,user)
        with patch("notifications.linking.DomainEventService.publish",side_effect=RuntimeError("outbox")):
            with self.assertRaises(RuntimeError):TelegramLinkService.consume(raw,99,99,{})
        token.refresh_from_db();self.assertIsNone(token.used_at);self.assertFalse(TelegramAccount.objects.filter(employee=emp).exists());self.assertFalse(AuditEvent.objects.filter(action="notification.telegram.linked").exists())

class ExternalDeliveryTests(TestCase):
    @override_settings(NOTIFICATIONS_TELEGRAM_ENABLED=True,NOTIFICATIONS_EMAIL_ENABLED=True,EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_routing_and_independent_telegram_email_delivery(self):
        _,emp=employee();TelegramAccount.objects.create(employee=emp,telegram_user_id=10,telegram_chat_id=20,linked_at=timezone.now());item=notification(emp);NotificationChannelRouter.route(item,"SLA_ESCALATION");self.assertEqual(set(item.deliveries.values_list("channel",flat=True)),{"in_app","telegram","email"})
        telegram=item.deliveries.get(channel="telegram");deliver_one(telegram,TelegramChannelHandler(FakeTelegram()));telegram.refresh_from_db();self.assertEqual(telegram.provider_message_id,"77")
        email=item.deliveries.get(channel="email");deliver_one(email,EmailChannelHandler(DjangoEmailProvider()));self.assertEqual(len(mail.outbox),1);self.assertEqual(mail.outbox[0].to,["personx@example.com"])
    @override_settings(NOTIFICATIONS_TELEGRAM_ENABLED=True,NOTIFICATIONS_EMAIL_ENABLED=True)
    def test_missing_identity_and_preferences_are_diagnostic(self):
        _,emp=employee(email="");NotificationPreference.objects.create(employee=emp,reason="SLA_ESCALATION",channel="telegram",enabled=False);item=notification(emp);NotificationChannelRouter.route(item,"SLA_ESCALATION");self.assertEqual(item.deliveries.get(channel="telegram").last_error_code,"PREFERENCE_DISABLED");self.assertEqual(item.deliveries.get(channel="email").last_error_code,"RECIPIENT_EMAIL_MISSING");self.assertEqual(item.deliveries.get(channel="in_app").status,"pending")
    def test_retry_after_permanent_and_ambiguous_outcome(self):
        _,emp=employee();item=notification(emp);delivery=NotificationDelivery.objects.create(notification=item,channel="telegram",status="processing")
        with self.assertRaises(ProviderFailure):deliver_one(delivery,FailureHandler(ProviderFailure("TELEGRAM_RATE_LIMITED",retryable=True,retry_after=20)))
        delivery.refresh_from_db();self.assertEqual(delivery.status,"retry");self.assertGreaterEqual(delivery.next_attempt_at,timezone.now()+timedelta(seconds=18))
        delivery.status="processing";delivery.save();
        with self.assertRaises(ProviderFailure):deliver_one(delivery,FailureHandler(ProviderFailure("TELEGRAM_BOT_BLOCKED")))
        delivery.refresh_from_db();self.assertEqual(delivery.status,"failed")
        delivery.status="processing";delivery.save()
        with self.assertRaises(ProviderFailure):deliver_one(delivery,FailureHandler(ProviderFailure("NETWORK",ambiguous=True)))
        delivery.refresh_from_db();self.assertEqual(delivery.status,"unknown")
    def test_stale_reconciliation_never_retries_ambiguous_dispatch(self):
        _,emp=employee();item=notification(emp);old=timezone.now()-timedelta(minutes=10);delivery=NotificationDelivery.objects.create(notification=item,channel="telegram",status="processing",processing_started_at=old,provider_started_at=old);reconcile_deliveries();delivery.refresh_from_db();self.assertEqual(delivery.status,"unknown");self.assertEqual(delivery.last_error_code,"DELIVERY_OUTCOME_UNKNOWN")
    def test_quiet_hours_overnight_and_dst_timezone(self):
        _,emp=employee();NotificationQuietHours.objects.create(employee=emp,enabled=True,timezone="Europe/Berlin",starts_at=time(22),ends_at=time(8));now=datetime(2026,3,29,0,30,tzinfo=dt_timezone.utc);end=quiet_hours_end(emp,now);self.assertEqual(end.astimezone(dt_timezone.utc),datetime(2026,3,29,6,0,tzinfo=dt_timezone.utc))
    @override_settings(NOTIFICATIONS_TELEGRAM_ENABLED=False,NOTIFICATIONS_EMAIL_ENABLED=False)
    def test_global_switch_suppresses_without_provider_call(self):
        _,emp=employee();item=notification(emp);NotificationChannelRouter.route(item,"SLA_ESCALATION");self.assertEqual(item.deliveries.get(channel="telegram").last_error_code,"CHANNEL_DISABLED")
    def test_subject_header_injection_is_removed(self):
        from .channels import channel_content
        _,emp=employee();item=notification(emp);item.title="Safe\r\nBcc: attacker@example.com";subject,_=channel_content(item,"email");self.assertNotIn("\n",subject);self.assertNotIn("\r",subject)

class TelegramConcurrencyTests(TransactionTestCase):
    @skipUnless(connection.vendor=="postgresql","PostgreSQL linking concurrency test")
    def test_concurrent_relink_preserves_one_active_binding(self):
        user,emp=employee("concurrent");raw1,_=TelegramLinkService.issue(emp,user);raw2,_=TelegramLinkService.issue(emp,user)
        # issue() revokes the previous token by design; make both valid to exercise the DB constraint race.
        TelegramLinkToken.objects.filter(token_hash__isnull=False).update(revoked_at=None)
        def run(args):
            raw,identity=args;close_old_connections()
            try:TelegramLinkService.consume(raw,identity,identity,{})
            except Exception:pass
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(run,[(raw1,101),(raw2,202)]))
        self.assertEqual(TelegramAccount.objects.filter(employee=emp,is_active=True).count(),1)
