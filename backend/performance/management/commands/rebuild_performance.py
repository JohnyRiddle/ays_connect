from datetime import datetime
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from employees.models import Employee

from performance.engine import aggregate_employee, build_facts


class Command(BaseCommand):
    help = "Idempotently rebuild performance facts and aggregates for a closed [from,to) period."

    def add_arguments(self, parser):
        parser.add_argument("--from", dest="period_from", required=True)
        parser.add_argument("--to", dest="period_to", required=True)
        parser.add_argument("--timezone", default="Asia/Novosibirsk")

    def handle(self, *args, **options):
        try:
            zone = ZoneInfo(options["timezone"])
            start = datetime.fromisoformat(options["period_from"]).replace(tzinfo=zone) if "T" not in options["period_from"] else datetime.fromisoformat(options["period_from"])
            end = datetime.fromisoformat(options["period_to"]).replace(tzinfo=zone) if "T" not in options["period_to"] else datetime.fromisoformat(options["period_to"])
        except (ValueError, KeyError) as exc: raise CommandError(str(exc)) from exc
        if start >= end: raise CommandError("--from must be before --to")
        count = build_facts(start, end)
        for employee in Employee.objects.iterator(chunk_size=500):
            aggregate_employee(employee, start, end, options["timezone"])
        self.stdout.write(self.style.SUCCESS(f"facts={count} employees={Employee.objects.count()} period=[{start},{end})"))
