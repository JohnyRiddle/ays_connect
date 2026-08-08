from django.core.management.base import BaseCommand
from notifications.models import Notification
class Command(BaseCommand):
    help="Имитирует отправку уведомлений в Telegram без внешней передачи данных"
    def handle(self,*args,**kwargs):
        count=Notification.objects.filter(telegram_status="pending").update(telegram_status="mock_sent")
        self.stdout.write(self.style.SUCCESS(f"Telegram mock: обработано {count} уведомлений"))
