from datetime import datetime
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from employees.models import Employee

from performance.engine import aggregate_employee, build_facts
from performance.models import PerformanceAggregate
import time


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
        started=time.monotonic(); count = build_facts(start, end)
        for employee in Employee.objects.iterator(chunk_size=500):
            aggregate_employee(employee, start, end, options["timezone"])
        aggregates=PerformanceAggregate.objects.filter(period_from=start,period_to=end,reporting_timezone=options["timezone"]).count();duration=time.monotonic()-started
        self.stdout.write(self.style.SUCCESS(f"period=[{start},{end}) facts={count} aggregates={aggregates} employees={Employee.objects.count()} duration_seconds={duration:.3f} errors=0"))
