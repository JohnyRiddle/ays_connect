from django.core.management.base import BaseCommand
from feedback.delivery import deliver_batch
import time
from django.db import close_old_connections


class Command(BaseCommand):
    help = "Deliver only private owner feedback (independent opt-in; no general notifications)."

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true")

    def handle(self, *args, **options):
        while True:
            if options["loop"]:
                close_old_connections()
            self.stdout.write(f"Processed: {deliver_batch()}")
            if not options["loop"]:
                return
            time.sleep(30)
