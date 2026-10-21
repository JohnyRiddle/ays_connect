import uuid
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from accounts.models import User
from employees.models import Employee
from notifications.models import TelegramAccount, Notification
from notifications.channels import ProviderResult, ProviderFailure
from audit.models import AuditEvent
from events.models import OutboxEvent
from .models import Feedback
from .delivery import deliver_batch


class FeedbackTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.owner = User.objects.create_user(username="owner", email="ivan@ays-connect.ru", is_staff=True, is_superuser=True)
        self.employee = Employee.objects.create(user=self.owner)
        self.author = User.objects.create_user(username="writer", email="writer@example.test")
        Employee.objects.create(user=self.author)
        self.admin = User.objects.create_user(username="admin", email="admin@example.test", is_staff=True, is_superuser=True)
        Employee.objects.create(user=self.admin)
        self.config = override_settings(FEEDBACK_OWNER_USER_ID=str(self.owner.pk), FEEDBACK_OWNER_EMPLOYEE_ID=str(self.employee.pk), FEEDBACK_TELEGRAM_ENABLED=True, TELEGRAM_BOT_TOKEN="synthetic-never-used", NOTIFICATIONS_TELEGRAM_ENABLED=False)
        self.config.enable(); self.addCleanup(self.config.disable)
        bot = patch("feedback.delivery.TelegramBotClient.call", return_value={"is_bot": True, "username": "AYS_ai_expert_bot"})
        bot.start(); self.addCleanup(bot.stop)
        self.client = APIClient()
        self.client.force_authenticate(self.author)
        self.payload = {"kind": "bug", "text": "Private full body <b>plain text</b>", "command_id": str(uuid.uuid4())}

    def submit(self):
        return self.client.post("/api/internal/v1/feedback/submit/", self.payload, format="json")

    def binding(self):
        return TelegramAccount.objects.create(employee=self.employee, telegram_user_id=100001, telegram_chat_id=100001, linked_at=timezone.now())

    def item(self):
        return Feedback.objects.create(author=self.author, **self.payload)

    def test_submission_idempotency_and_conflict(self):
        self.assertEqual(self.submit().status_code, 201)
        self.assertEqual(self.submit().status_code, 200)
        self.payload["text"] = "changed"
        self.assertEqual(self.submit().status_code, 409)
        self.assertEqual(Feedback.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.filter(action="feedback.submitted").count(), 1)
        self.assertEqual(OutboxEvent.objects.filter(event_type="feedback.submitted").count(), 1)

    def test_private_body_never_in_shared_channels(self):
        response = self.submit()
        self.assertNotIn("text", response.data)
        self.assertNotIn(self.payload["text"], str(list(AuditEvent.objects.values())) + str(list(OutboxEvent.objects.values())))
        self.assertFalse(Notification.objects.exists())

    def test_validation_and_no_automatic_metadata(self):
        for change in ({"text": "   "}, {"text": "x" * 3001}, {"kind": "other"}, {"url": "secret"}, {"command_id": "invalid"}):
            with self.subTest(change=next(iter(change))):
                data = self.payload | change
                self.assertEqual(self.client.post("/api/internal/v1/feedback/submit/", data, format="json").status_code, 400)
        self.assertFalse(Feedback.objects.exists())

    def test_owner_only_list_detail_and_admin(self):
        item = self.item()
        for user in (self.author, self.admin):
            self.client.force_authenticate(user)
            for path in ("/api/internal/v1/feedback/", f"/api/internal/v1/feedback/{item.pk}/"):
                self.assertEqual(self.client.get(path).status_code, 403)
            self.client.force_login(user)
            for path in ("/admin/feedback/feedback/", f"/admin/feedback/feedback/{item.pk}/change/"):
                self.assertNotIn(self.payload["text"], self.client.get(path).content.decode())
        self.client.force_authenticate(self.owner)
        response = self.client.get("/api/internal/v1/feedback/")
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(self.client.get(f"/api/internal/v1/feedback/{item.pk}/").data["text"], self.payload["text"])
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(f"/admin/feedback/feedback/{item.pk}/change/").status_code, 200)

    def test_fail_closed_identity_and_inactive(self):
        self.client.force_authenticate(self.owner)
        for config in ({"FEEDBACK_OWNER_USER_ID": ""}, {"FEEDBACK_OWNER_EMPLOYEE_ID": "invalid"}, {"FEEDBACK_OWNER_USER_ID": "invalid"}, {"FEEDBACK_OWNER_EMPLOYEE_ID": str(uuid.uuid4())}, {"FEEDBACK_OWNER_USER_ID": str(self.admin.pk)}):
            with override_settings(**config):
                self.assertEqual(self.client.get("/api/internal/v1/feedback/").status_code, 403)
        self.employee.account_access_state = "blocked"; self.employee.save()
        self.assertEqual(self.client.get("/api/internal/v1/feedback/").status_code, 403)
        self.assertEqual(self.submit().status_code, 403)

    def test_anonymous_and_methods(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.submit().status_code, 401)
        self.client.force_authenticate(self.owner)
        item = self.item()
        for method in (self.client.patch, self.client.delete):
            self.assertEqual(method(f"/api/internal/v1/feedback/{item.pk}/").status_code, 405)

    def test_retry_owner_only_and_explicit_confirmation(self):
        item = self.item()
        Feedback.objects.filter(pk=item.pk).update(delivery_status="unknown")
        url = f"/api/internal/v1/feedback/{item.pk}/retry/"
        for user in (self.author, self.admin):
            self.client.force_authenticate(user)
            self.assertEqual(self.client.post(url, {"confirmed_not_received": True}, format="json").status_code, 403)
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.post(url, {}, format="json").status_code, 400)
        self.assertEqual(self.client.post(url, {"confirmed_not_received": True}, format="json").status_code, 200)
        self.assertEqual(self.client.post(url, {"confirmed_not_received": True}, format="json").status_code, 409)

    @patch("feedback.delivery.TelegramBotClient.send_message")
    def test_revoked_or_group_binding_never_receives_body(self, send):
        binding = self.binding(); item = self.item()
        for changes in ({"is_active": False}, {"is_active": True, "telegram_chat_id": -100001}, {"telegram_chat_id": 100001, "delivery_disabled_at": timezone.now()}):
            TelegramAccount.objects.filter(pk=binding.pk).update(**changes)
            Feedback.objects.filter(pk=item.pk).update(next_attempt_at=None)
            deliver_batch()
        send.assert_not_called()

    @patch("feedback.delivery.TelegramBotClient.send_message")
    def test_delivery_full_text_only_verified_owner_once(self, send):
        self.binding(); item = self.item(); send.return_value = ProviderResult("123")
        self.assertEqual(deliver_batch(), 1); self.assertEqual(deliver_batch(), 0)
        send.assert_called_once()
        self.assertEqual(send.call_args.args[0], 100001)
        self.assertTrue(send.call_args.args[1].endswith(self.payload["text"]))
        item.refresh_from_db(); self.assertEqual(item.delivery_status, "delivered")
        self.assertFalse(Notification.objects.exists())

    @patch("feedback.delivery.TelegramBotClient.send_message")
    def test_unbound_disabled_and_foreign_binding_preserve_queue(self, send):
        item = self.item()
        TelegramAccount.objects.create(employee=self.author.employee, telegram_user_id=200001, telegram_chat_id=200001, linked_at=timezone.now())
        deliver_batch(); item.refresh_from_db(); self.assertEqual(item.delivery_status, "pending")
        self.assertEqual(item.error_code, "OWNER_BINDING_UNAVAILABLE"); send.assert_not_called()
        with override_settings(FEEDBACK_TELEGRAM_ENABLED=False):
            self.assertEqual(deliver_batch(), 0)

    @patch("feedback.delivery.TelegramBotClient.send_message")
    def test_rate_limit_retries_with_backoff(self, send):
        self.binding(); item = self.item()
        send.side_effect = ProviderFailure("TELEGRAM_RATE_LIMITED", retryable=True, retry_after=120)
        deliver_batch(); deliver_batch(); self.assertEqual(send.call_count, 1)
        item.refresh_from_db(); self.assertEqual(item.delivery_status, "pending")
        Feedback.objects.filter(pk=item.pk).update(next_attempt_at=timezone.now()-timedelta(seconds=1))
        send.side_effect = None; send.return_value = ProviderResult("124")
        deliver_batch(); item.refresh_from_db(); self.assertEqual(item.delivery_status, "delivered")

    @patch("feedback.delivery.TelegramBotClient.send_message")
    def test_ambiguous_and_provider_5xx_are_not_blindly_retried(self, send):
        self.binding()
        for error in (ProviderFailure("TELEGRAM_NETWORK_ERROR", ambiguous=True), ProviderFailure("TELEGRAM_PROVIDER_UNAVAILABLE", retryable=True), ValueError("secret")):
            self.payload["command_id"] = uuid.uuid4(); item = self.item(); send.side_effect = error
            deliver_batch(); item.refresh_from_db(); self.assertEqual(item.delivery_status, "unknown")
            calls = send.call_count; deliver_batch(); self.assertEqual(send.call_count, calls)
            self.assertNotIn("secret", item.error_code)

    @patch("feedback.delivery.TelegramBotClient.send_message")
    def test_crash_after_claim_and_blocked_bot(self, send):
        self.binding(); item = self.item()
        Feedback.objects.filter(pk=item.pk).update(delivery_status="sending", started_at=timezone.now()-timedelta(minutes=6))
        deliver_batch(); item.refresh_from_db(); self.assertEqual(item.delivery_status, "unknown"); send.assert_not_called()
        self.payload["command_id"] = uuid.uuid4(); item = self.item()
        send.side_effect = ProviderFailure("TELEGRAM_BOT_BLOCKED")
        deliver_batch(); item.refresh_from_db(); self.assertEqual(item.delivery_status, "failed")
        self.assertEqual(Feedback.objects.count(), 2)

    @patch("feedback.delivery.TelegramBotClient.send_message")
    def test_wrong_bot_cannot_receive_private_body(self, send):
        self.binding(); item = self.item()
        with patch("feedback.delivery.TelegramBotClient.call", return_value={"is_bot": True, "username": "other_bot"}):
            deliver_batch()
        send.assert_not_called()
        item.refresh_from_db(); self.assertEqual(item.error_code, "BOT_IDENTITY_UNVERIFIED")

    @patch("feedback.delivery.TelegramBotClient.send_message")
    def test_binding_revoked_during_preflight_never_sends(self, send):
        binding = self.binding(); self.item()
        def revoke():
            TelegramAccount.objects.filter(pk=binding.pk).update(is_active=False)
            return True
        with patch("feedback.delivery.verify_bot", side_effect=revoke):
            deliver_batch()
        send.assert_not_called()

    @patch("feedback.delivery.TelegramBotClient.send_message")
    def test_late_old_outcome_cannot_overwrite_explicit_retry(self, send):
        self.binding(); item = self.item()
        def old_outcome(*args):
            Feedback.objects.filter(pk=item.pk).update(delivery_status="pending", lease_token=None)
            return ProviderResult("old-attempt")
        send.side_effect = old_outcome
        deliver_batch(); item.refresh_from_db()
        self.assertEqual(item.delivery_status, "pending")
        self.assertEqual(item.provider_message_id, "")

    def test_non_owner_staff_with_model_permissions_still_denied(self):
        from django.contrib.auth.models import Permission
        self.admin.is_superuser = False; self.admin.save()
        self.admin.user_permissions.add(*Permission.objects.filter(content_type__app_label="feedback"))
        item = self.item(); self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get("/api/internal/v1/feedback/").status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get("/admin/feedback/feedback/").status_code, 403)
        self.assertEqual(self.client.get(f"/admin/feedback/feedback/{item.pk}/change/").status_code, 403)

    @patch("feedback.delivery.TelegramBotClient.send_message")
    def test_worker_output_and_records_never_contain_provider_secret(self, send):
        from io import StringIO
        from django.core.management import call_command
        self.binding(); item = self.item()
        send.side_effect = ProviderFailure("TELEGRAM_NETWORK_ERROR", "secret-token-url", ambiguous=True)
        output = StringIO(); errors = StringIO()
        call_command("deliver_feedback", stdout=output, stderr=errors)
        self.assertNotIn(self.payload["text"], output.getvalue() + errors.getvalue())
        self.assertNotIn("secret-token-url", output.getvalue() + errors.getvalue())
        item.refresh_from_db(); self.assertEqual(item.error_code, "TELEGRAM_NETWORK_ERROR")


from concurrent.futures import ThreadPoolExecutor
from threading import Event
from django.test import TransactionTestCase
from django.db import connections


class FeedbackConcurrencyTests(TransactionTestCase):
    def test_simultaneous_submission_has_one_record_and_event(self):
        user = User.objects.create_user(username="race", email="race@example.test")
        Employee.objects.create(user=user)
        payload = {"command_id": str(uuid.uuid4()), "kind": "bug", "text": "Synthetic concurrent request"}
        def submit():
            try:
                client = APIClient(); client.force_authenticate(User.objects.get(pk=user.pk))
                return client.post("/api/internal/v1/feedback/submit/", payload, format="json").status_code
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(submit) for _ in range(2)]
            self.assertEqual(sorted(f.result(timeout=15) for f in futures), [200, 201])
        self.assertEqual(Feedback.objects.count(), 1)
        self.assertEqual(OutboxEvent.objects.filter(event_type="feedback.submitted").count(), 1)

    def test_parallel_workers_send_only_once(self):
        owner = User.objects.create_user(username="owner", email="ivan@ays-connect.ru")
        employee = Employee.objects.create(user=owner)
        TelegramAccount.objects.create(employee=employee, telegram_user_id=100001, telegram_chat_id=100001, linked_at=timezone.now())
        Feedback.objects.create(author=owner, command_id=uuid.uuid4(), kind="bug", text="Synthetic concurrent delivery")
        started, release = Event(), Event()
        def send(*args):
            started.set(); release.wait(10)
            return ProviderResult("race-123")
        def worker():
            try:
                return deliver_batch()
            finally:
                connections.close_all()
        with override_settings(FEEDBACK_OWNER_USER_ID=str(owner.pk), FEEDBACK_OWNER_EMPLOYEE_ID=str(employee.pk), FEEDBACK_TELEGRAM_ENABLED=True, TELEGRAM_BOT_TOKEN="synthetic"), patch("feedback.delivery.verify_bot", return_value=True), patch("feedback.delivery.TelegramBotClient.send_message", side_effect=send) as sender:
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(worker)
                self.assertTrue(started.wait(10))
                second = pool.submit(worker)
                try:
                    self.assertEqual(second.result(timeout=10), 0)
                finally:
                    release.set()
                self.assertEqual(first.result(timeout=10), 1)
            sender.assert_called_once()
