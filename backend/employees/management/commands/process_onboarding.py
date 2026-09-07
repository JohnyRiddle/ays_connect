from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from employees.models import EmployeeInvitation, OnboardingInstance, OnboardingStepInstance
from employees.onboarding import _event
from employees.onboarding_lifecycle import OnboardingService, ResponsibleResolver


class Command(BaseCommand):
    help = "Reconciles invitation and onboarding lifecycle state in bounded PostgreSQL-safe batches."

    def add_arguments(self, parser):
        parser.add_argument("--batch-size", type=int, default=100)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        size = max(1, min(options["batch_size"], 1000)); dry_run = options["dry_run"]
        expired = reconciled = resolved = 0
        with transaction.atomic():
            invitations = list(EmployeeInvitation.objects.select_for_update(skip_locked=True).filter(used_at__isnull=True, revoked_at__isnull=True, expires_at__lte=timezone.now())[:size])
            for invitation in invitations:
                expired += 1
                if not dry_run:
                    invitation.status = "expired"; invitation.version += 1; invitation.save(update_fields=["status", "version"])
                    _event("people.invitation.expired", invitation, new={"employee_id": str(invitation.employee_id)})
            instances = list(OnboardingInstance.objects.select_for_update(skip_locked=True).filter(status__in=["pending", "active", "paused"])[:size])
            for instance in instances:
                reconciled += 1
                if not dry_run: OnboardingService.reconcile(instance)
            blocked = list(OnboardingStepInstance.objects.select_for_update(skip_locked=True).select_related("template_step", "onboarding__employee").filter(status="blocked", responsible_employee__isnull=True)[:size])
            for step in blocked:
                try: employee, detail = ResponsibleResolver.resolve(step.template_step, step.onboarding.employee)
                except Exception: continue
                resolved += 1
                if not dry_run:
                    step.responsible_employee=employee; step.resolution_detail=detail; step.status="pending"; step.version+=1; step.save(update_fields=["responsible_employee","resolution_detail","status","version","updated_at"])
            if dry_run: transaction.set_rollback(True)
        self.stdout.write(f"expired={expired} reconciled={reconciled} resolved={resolved} dry_run={dry_run}")
