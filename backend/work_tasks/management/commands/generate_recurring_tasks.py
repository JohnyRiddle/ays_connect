from django.core.management.base import BaseCommand

from work_tasks.automation import RecurrenceService
from operations.heartbeat import record_worker_cycle


class Command(BaseCommand):
    help = "Генерирует production Tasks для recurring occurrences в настроенном horizon"

    def handle(self, *args, **options):
        count = RecurrenceService.generate_due_occurrences()
        record_worker_cycle("recurrence", processed=count)
        self.stdout.write(self.style.SUCCESS(f"Recurring occurrences processed: {count}"))
