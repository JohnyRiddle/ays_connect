from django.core.management.base import BaseCommand
from tasks.scheduler import run_due_schedules
from learning.scheduler import process_learning_deadlines
from operations.heartbeat import record_worker_cycle


class Command(BaseCommand):
    help="Создаёт задачи и чек-листы, срок запуска которых наступил"

    def handle(self,*args,**options):
        result=run_due_schedules()
        learning=process_learning_deadlines()
        learning_processed = sum(learning.values())
        record_worker_cycle(
            "schedule",
            processed=result["tasks"] + result["checklists"] + learning_processed,
            metadata={"skipped": result["skipped"], "learning": learning},
        )
        self.stdout.write(self.style.SUCCESS(f"tasks={result['tasks']} checklists={result['checklists']} skipped={result['skipped']} learning={learning}"))
