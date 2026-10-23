"""Private durable queue. Never enters the broad notification delivery pipeline."""
from datetime import timedelta
import uuid
from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from notifications.channels import TelegramBotClient, ProviderFailure
from notifications.models import TelegramAccount
from .models import Feedback
from .permissions import owner_employee

EXPECTED_BOT = "AYS_ai_expert_bot"


def verify_bot():
    try:
        result = TelegramBotClient().call("getMe", {})
        return result.get("is_bot") is True and result.get("username", "").lower() == EXPECTED_BOT.lower()
    except Exception:
        return False


def deliver_batch(limit=25):
    if not settings.FEEDBACK_TELEGRAM_ENABLED:
        return 0
    now = timezone.now()
    # A process may die after Telegram accepts a message. Never resend it blindly.
    Feedback.objects.filter(delivery_status="sending", started_at__lt=now-timedelta(minutes=5)).update(
        delivery_status="unknown", error_code="INTERRUPTED_SEND")
    ids = Feedback.objects.filter(delivery_status="pending").filter(
        Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now)
    ).order_by("created_at").values_list("pk", flat=True)[:limit]
    count = 0
    bot_verified = None
    for pk in list(ids):
        lease = uuid.uuid4()
        # Atomic compare-and-set prevents parallel workers from sending twice.
        if not Feedback.objects.filter(pk=pk, delivery_status="pending").filter(
            Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now)
        ).update(delivery_status="sending", started_at=timezone.now(), lease_token=lease):
            continue
        claimed = Feedback.objects.filter(pk=pk, lease_token=lease)
        item = Feedback.objects.get(pk=pk)
        owner = owner_employee()
        account = TelegramAccount.objects.filter(employee=owner, is_active=True,
            delivery_disabled_at__isnull=True).first() if owner else None
        valid = account and account.telegram_chat_id > 0 and account.telegram_chat_id == account.telegram_user_id
        if not valid or not settings.TELEGRAM_BOT_TOKEN:
            claimed.update(delivery_status="pending",
                error_code="OWNER_BINDING_UNAVAILABLE" if not valid else "BOT_NOT_CONFIGURED",
                next_attempt_at=now+timedelta(minutes=5))
            continue
        if bot_verified is None:
            bot_verified = verify_bot()
        if not bot_verified:
            claimed.update(delivery_status="pending", error_code="BOT_IDENTITY_UNVERIFIED",
                next_attempt_at=now+timedelta(minutes=5))
            continue
        # getMe may take time. Recheck the owner and exact binding before send,
        # and refuse a claim expired/revoked while this worker was paused.
        current_owner = owner_employee()
        if not current_owner or current_owner.pk != owner.pk or not TelegramAccount.objects.filter(
            pk=account.pk, employee=current_owner, is_active=True, delivery_disabled_at__isnull=True,
            telegram_chat_id=account.telegram_chat_id, telegram_user_id=account.telegram_chat_id,
        ).exists():
            claimed.filter(delivery_status="sending").update(delivery_status="pending",
                error_code="OWNER_BINDING_UNAVAILABLE", next_attempt_at=timezone.now()+timedelta(minutes=5))
            continue
        item.attempts += 1
        if not claimed.filter(delivery_status="sending").update(attempts=item.attempts):
            continue
        name = (item.author.get_full_name() or item.author.email)[:120]
        text = f"AYS Connect · Обратная связь\n{item.get_kind_display()}\nОт: {name}\nID: {item.pk}\n\n{item.text}"
        try:
            result = TelegramBotClient().send_message(account.telegram_chat_id, text)
            if not result.message_id:
                raise ProviderFailure("MISSING_MESSAGE_ID", ambiguous=True)
        except ProviderFailure as exc:
            # Only an explicit 429 is certainly rejected before send. HTTP 5xx and
            # network failures may follow acceptance and therefore need review.
            retry = exc.code == "TELEGRAM_RATE_LIMITED" and not exc.ambiguous
            unknown = exc.ambiguous or exc.code == "TELEGRAM_PROVIDER_UNAVAILABLE"
            delay = max(60, min(86400, int(exc.retry_after or 0)), min(3600, 60 * 2 ** min(item.attempts, 6)))
            claimed.update(delivery_status="pending" if retry else "unknown" if unknown else "failed",
                error_code=exc.code[:64], next_attempt_at=now+timedelta(seconds=delay) if retry else None)
        except Exception:
            # No raw exception, URL, token, or message body is logged.
            claimed.update(delivery_status="unknown", error_code="UNEXPECTED_SEND_OUTCOME")
        else:
            claimed.update(delivery_status="delivered", error_code="",
                provider_message_id=result.message_id, delivered_at=timezone.now(), next_attempt_at=None)
        count += 1
    return count
