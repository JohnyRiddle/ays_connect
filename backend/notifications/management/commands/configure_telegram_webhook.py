from django.conf import settings
from django.core.management.base import BaseCommand,CommandError
from notifications.channels import TelegramBotClient
class Command(BaseCommand):
    help="Configure Telegram webhook without exposing credentials"
    def handle(self,*args,**options):
        if not settings.TELEGRAM_WEBHOOK_URL or not settings.TELEGRAM_WEBHOOK_SECRET or not settings.TELEGRAM_BOT_TOKEN:raise CommandError("Telegram webhook configuration is incomplete")
        TelegramBotClient().set_webhook(settings.TELEGRAM_WEBHOOK_URL,settings.TELEGRAM_WEBHOOK_SECRET);self.stdout.write(self.style.SUCCESS("Telegram webhook configured"))
