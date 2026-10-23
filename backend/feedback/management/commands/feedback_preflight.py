"""Read-only identity/config check; never prints credentials or raw provider data."""
import json
from django.conf import settings
from django.core.management.base import BaseCommand
from accounts.models import User
from feedback.permissions import OWNER_EMAIL, owner_employee
from feedback.delivery import verify_bot, EXPECTED_BOT
from notifications.models import TelegramAccount


class Command(BaseCommand):
    help = "Read-only owner/binding checks; optional getMe only, no messages or grants."

    def add_arguments(self, parser):
        parser.add_argument("--check-bot", action="store_true")

    def handle(self, *args, **options):
        users = list(User.objects.filter(email=OWNER_EMAIL).select_related("employee"))
        candidate = users[0] if len(users) == 1 else None
        employee = getattr(candidate, "employee", None)
        owner = owner_employee()
        binding = TelegramAccount.objects.filter(employee=owner, is_active=True,
            delivery_disabled_at__isnull=True).first() if owner else None
        self.stdout.write(json.dumps({
            "owner_email_unique": len(users) == 1,
            "candidate_user_id": candidate.pk if candidate else None,
            "candidate_employee_id": str(employee.pk) if employee else None,
            "owner_pins_match_active_identity": bool(owner),
            "active_private_binding": bool(binding and binding.telegram_chat_id > 0 and binding.telegram_chat_id == binding.telegram_user_id),
            "expected_bot": EXPECTED_BOT,
            "bot_token_present": bool(settings.TELEGRAM_BOT_TOKEN),
            "bot_verified": verify_bot() if options["check_bot"] else "not_checked",
            "feedback_delivery_enabled": settings.FEEDBACK_TELEGRAM_ENABLED,
            "general_notifications_enabled": settings.NOTIFICATIONS_TELEGRAM_ENABLED,
        }))
