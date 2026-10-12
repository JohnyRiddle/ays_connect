"""Explicit consumer for onboarding emails to people without an Employee/User.

No raw capability is queued or logged. Provider acceptance is not inbox delivery.
Ambiguous SMTP outcomes stop automatic retry; explicit resend rotates generation.
"""
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from events.models import OutboxEvent
from notifications.channels import DjangoEmailProvider, ProviderFailure
from .models import EmployeeInvitation, RegistrationRequest
from .registration import User, locations_for, signed_token, verification_token

EVENTS = ("registration.mail.requested", "registration.invite_mail.requested")


def messages(event):
    base = settings.FRONTEND_BASE_URL
    if event.event_type == "registration.invite_mail.requested":
        item = EmployeeInvitation.objects.get(pk=event.entity_id)
        if item.used_at or item.revoked_at or item.expires_at <= timezone.now() or item.version != event.payload["generation"]:
            return []
        token = signed_token(item, "invite", item.version)
        return [(item.delivery_address, "Приглашение в AYS Connect", f"Объект: {item.employment_location.name}\n{base}/register#invite={token}")]
    item = RegistrationRequest.objects.get(pk=event.entity_id)
    kind = event.payload["kind"]
    if kind == "verify":
        if item.status != "email_pending" or item.mail_generation != event.payload["generation"] or item.expires_at <= timezone.now():
            return []
        return [(item.email, "Подтверждение email AYS Connect", f"Подтвердите адрес: {base}/register#verify={verification_token(item)}")]
    if kind == "review":
        if item.status != "pending":
            return []
        recipients = [user.email for user in User.objects.filter(is_active=True)
                      if locations_for(user, "people.registration.manage").filter(pk=item.employment_location_id).exists()]
        return [(email, "Новая заявка AYS Connect", f"Новая подтверждённая заявка. Откройте {base}/people/registration") for email in recipients]
    return [(item.email, "Решение по регистрации AYS Connect",
             "Заявка одобрена. Можно войти в AYS Connect." if kind == "approved" else f"Заявка отклонена: {item.rejection_code}")]


def process_mail(batch_size=100, provider=None):
    if not settings.NOTIFICATIONS_EMAIL_ENABLED:
        return 0
    # Console/file/dummy backends would expose capabilities or falsely count delivery.
    if provider is None and settings.EMAIL_BACKEND != "django.core.mail.backends.smtp.EmailBackend":
        return 0
    provider = provider or DjangoEmailProvider()
    ids = list(OutboxEvent.objects.filter(event_type__in=EVENTS).filter(
        Q(status="pending") | Q(status="failed", next_attempt_at__lte=timezone.now(), attempts__lt=5)
    ).order_by("created_at").values_list("pk", flat=True)[:batch_size])
    handled = 0
    for pk in ids:
        with transaction.atomic():
            event = OutboxEvent.objects.select_for_update(skip_locked=True).filter(pk=pk).first()
            if not event or event.status == "processed" or (event.status == "failed" and not event.next_attempt_at):
                continue
            event.attempts += 1
            sent = set(event.payload.get("accepted_recipients", []))
            # Commit an ambiguity marker BEFORE contacting SMTP. A worker crash
            # after provider acceptance must never make the event pending again.
            event.status = "failed"
            event.last_error_code = "DELIVERY_OUTCOME_UNKNOWN"
            event.failed_at = timezone.now()
            event.next_attempt_at = None
            event.save(update_fields=["attempts", "status", "last_error_code", "failed_at", "next_attempt_at"])
        try:
            outgoing = messages(event)
            for email, title, body in outgoing:
                if email in sent:
                    continue
                provider.send(email, title, body)
                sent.add(email)
                with transaction.atomic():
                    locked = OutboxEvent.objects.select_for_update().get(pk=pk)
                    locked.payload = {**locked.payload, "accepted_recipients": sorted(sent)}
                    locked.save(update_fields=["payload"])
            event.status = "processed"
            event.processed_at = timezone.now()
            event.last_error_code = "NO_ELIGIBLE_RECIPIENT" if not outgoing else ""
            event.next_attempt_at = None
        except ProviderFailure as exc:
            event.status = "failed"
            event.last_error_code = "DELIVERY_OUTCOME_UNKNOWN" if exc.ambiguous else exc.code
            event.failed_at = timezone.now()
            event.next_attempt_at = (timezone.now() + timedelta(minutes=2 ** event.attempts)
                if exc.retryable and not exc.ambiguous and event.attempts < 5 else None)
        except Exception:
            event.status = "failed"
            event.last_error_code = "REGISTRATION_MAIL_ERROR"
            event.failed_at = timezone.now()
            event.next_attempt_at = None
        with transaction.atomic():
            OutboxEvent.objects.select_for_update().get(pk=pk)
            event.payload = {**event.payload, "accepted_recipients": sorted(sent)}
            event.save(update_fields=["attempts", "status", "processed_at", "last_error_code", "next_attempt_at", "failed_at", "payload"])
            handled += 1
    return handled
