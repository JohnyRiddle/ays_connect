import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest import skipUnless
from unittest.mock import patch
from django.db import close_old_connections,connection,connections
from django.test import TestCase,TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient
from accounts.models import User
from employees.models import Employee
from events.models import OutboxEvent
from audit.models import AuditEvent
from .models import Notification,NotificationDelivery,NotificationDeliveryAttempt,NotificationIntent,NotificationPreference,NotificationTemplate
from .services import ingest_event,preference_enabled,process_deliveries,render_template
def fixture(s="1"):
    u=User.objects.create_user(username=f"notify{s}",email=f"n{s}@test.local",password="pass12345");return u,Employee.objects.create(user=u,employee_number=f"N-{s}",first_name="Notify")
def event(e,event_id=None):return OutboxEvent.objects.create(event_id=event_id or uuid.uuid4(),event_type="notification.requested",entity_type="EscalationExecution",entity_id="1",occurred_at=timezone.now(),payload={"reason":"SLA_ESCALATION","recipient_employee_id":str(e.pk),"request_id":"42","level":2,"event_type":"breach"})
class NotificationCoreTests(TestCase):
    def test_ingestion_is_idempotent_and_creates_delivery(self):
        _,e=fixture();source=event(e);ingest_event(source);ingest_event(source);self.assertEqual(NotificationIntent.objects.count(),1);self.assertEqual(Notification.objects.count(),1);self.assertEqual(NotificationDelivery.objects.count(),3)
    def test_mandatory_escalation_ignores_disabled_preference(self):
        _,e=fixture();NotificationPreference.objects.create(employee=e,reason="SLA_ESCALATION",enabled=False);self.assertTrue(preference_enabled(e,"SLA_ESCALATION"))
    def test_safe_renderer(self):
        from rest_framework.exceptions import ValidationError
        with self.assertRaises(ValidationError):render_template("{user.password}",{"user":object()},["user.password"])
    def test_delivery_and_read_are_separate(self):
        u,e=fixture();ingest_event(event(e));process_deliveries();item=Notification.objects.get();self.assertIsNotNone(item.delivered_at);self.assertFalse(item.is_read);self.assertEqual(NotificationDeliveryAttempt.objects.count(),1);client=APIClient();client.force_authenticate(u);client.post(f"/api/v1/notifications/{item.pk}/read/");item.refresh_from_db();self.assertTrue(item.is_read)
    def test_inbox_idor_and_count(self):
        u,e=fixture();other,e2=fixture("2");ingest_event(event(e));ingest_event(event(e2));foreign=Notification.objects.get(recipient=other);client=APIClient();client.force_authenticate(u);self.assertEqual(client.get("/api/v1/notifications/").data["count"],1);self.assertEqual(client.get("/api/v1/notifications/unread-count/").data["count"],1);self.assertEqual(client.post(f"/api/v1/notifications/{foreign.pk}/read/").status_code,404)
    def test_template_permission_and_preview(self):
        u,_=fixture();u.is_superuser=True;u.save();client=APIClient();client.force_authenticate(u);t=NotificationTemplate.objects.create(code="TEST",name="Test",title_template="Hi {name}",body_template="Body",allowed_variables=["name"]);self.assertEqual(client.post(f"/api/v1/notifications/templates/{t.pk}/preview/",{"payload":{"name":"A"}},format="json").data["title"],"Hi A")
    def test_render_failure_has_no_notification(self):
        _,e=fixture();NotificationTemplate.objects.update_or_create(code="SLA_ESCALATION",defaults={"name":"Bad","title_template":"{missing}","body_template":"x","allowed_variables":[]})
        with self.assertRaises(Exception):ingest_event(event(e))
        self.assertEqual(Notification.objects.count(),0)
    def test_template_audit_and_outbox_rollback_together(self):
        u,_=fixture();u.is_superuser=True;u.save();client=APIClient();client.force_authenticate(u)
        with patch("notifications.views.DomainEventService.publish",side_effect=RuntimeError("outbox unavailable")):
            with self.assertRaises(RuntimeError):client.post("/api/v1/notifications/templates/",{"code":"ROLLBACK","name":"Rollback","title_template":"Title","body_template":"Body","allowed_variables":[]},format="json")
        self.assertFalse(NotificationTemplate.objects.filter(code="ROLLBACK").exists());self.assertFalse(AuditEvent.objects.filter(action="notification_template.created").exists())
class NotificationConcurrencyTests(TransactionTestCase):
    @skipUnless(connection.vendor=="postgresql","PostgreSQL concurrency test")
    def test_eight_concurrent_ingestions_create_one(self):
        _,e=fixture();source=event(e);pk=source.pk
        def run(_):
            close_old_connections()
            try:ingest_event(OutboxEvent.objects.get(pk=pk))
            except Exception:pass
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=8) as p:list(p.map(run,range(8)))
        self.assertEqual(NotificationIntent.objects.count(),1);self.assertEqual(Notification.objects.count(),1)
    @skipUnless(connection.vendor=="postgresql","PostgreSQL SKIP LOCKED test")
    def test_concurrent_workers_deliver_once(self):
        _,e=fixture();ingest_event(event(e))
        def run(_):close_old_connections();process_deliveries(1);connections.close_all()
        with ThreadPoolExecutor(max_workers=4) as p:list(p.map(run,range(4)))
        self.assertEqual(NotificationDeliveryAttempt.objects.count(),1)
