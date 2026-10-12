from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from employees.models import Employee, AssignmentTarget
from employees.assignment_targets import assignable_employees
from employees.services import EmployeeAssignmentTargetService


class Command(BaseCommand):
    help = "Preview missing employee assignment targets; --apply requires an active superuser actor."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--actor-id", type=int)

    @transaction.atomic
    def handle(self, *args, **options):
        actor = None
        if options["apply"]:
            actor = get_user_model().objects.filter(pk=options["actor_id"], is_active=True, is_superuser=True).first()
            if not actor:
                raise CommandError("--apply requires --actor-id of an active superuser.")
        missing = created = 0
        for employee in assignable_employees().order_by("pk"):
            if AssignmentTarget.objects.filter(target_type="employee", employee=employee).exists():
                continue
            missing += 1
            if options["apply"]:
                _, added = EmployeeAssignmentTargetService.ensure(employee=employee, actor_user=actor)
                created += int(added)
        self.stdout.write(f"mode={'apply' if options['apply'] else 'preview'} missing={missing} created={created}")
