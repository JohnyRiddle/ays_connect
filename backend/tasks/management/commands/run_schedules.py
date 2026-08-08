from django.core.management.base import BaseCommand
from tasks.scheduler import run_due_schedules
from learning.scheduler import process_learning_deadlines


class Command(BaseCommand):
    help="Создаёт задачи и чек-листы, срок запуска которых наступил"

    def handle(self,*args,**options):
        result=run_due_schedules()
        learning=process_learning_deadlines()
        self.stdout.write(self.style.SUCCESS(f"tasks={result['tasks']} checklists={result['checklists']} skipped={result['skipped']} learning={learning}"))
