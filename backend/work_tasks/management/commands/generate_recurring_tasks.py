from django.core.management.base import BaseCommand

from work_tasks.automation import RecurrenceService


class Command(BaseCommand):
    help = "Генерирует production Tasks для recurring occurrences в настроенном horizon"

    def handle(self, *args, **options):
        count = RecurrenceService.generate_due_occurrences()
        self.stdout.write(self.style.SUCCESS(f"Recurring occurrences processed: {count}"))
