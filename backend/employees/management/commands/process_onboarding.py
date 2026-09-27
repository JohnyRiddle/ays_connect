from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from employees.models import Employee, EmployeeInvitation, OnboardingInstance
from employees.onboarding import _event
from employees.onboarding_lifecycle import OnboardingService
from employees.onboarding_events import process_events, notify_overdue
from operations.heartbeat import record_worker_cycle


class Command(BaseCommand):
    help = "Reconciles invitation and onboarding lifecycle state in bounded PostgreSQL-safe batches."

    def add_arguments(self, parser):
        parser.add_argument("--batch-size", type=int, default=100)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        size=max(1,min(options['batch_size'],1000));dry=options['dry_run']
        expired=reconciled=0
        candidates=EmployeeInvitation.objects.filter(used_at__isnull=True,revoked_at__isnull=True,
            expires_at__lte=timezone.now()).exclude(status='expired').order_by('expires_at','pk')
        for pk,owner in list(candidates.values_list('pk','employee_id')[:size]):
            with transaction.atomic():
                if not Employee.objects.select_for_update(skip_locked=True).filter(pk=owner).exists():continue
                invitation=candidates.select_for_update().filter(pk=pk).first()
                if not invitation:continue
                expired+=1
                if not dry:
                    invitation.status='expired';invitation.version+=1
                    invitation.save(update_fields=['status','version'])
                    _event('people.invitation.expired',invitation,new={'employee_id':str(owner)})
        if not dry: process_events(size)
        candidates=OnboardingInstance.objects.filter(status__in=['pending','active','paused']).order_by('updated_at','pk')
        for pk,owner in list(candidates.values_list('pk','employee_id')[:size]):
            with transaction.atomic():
                if not Employee.objects.select_for_update(skip_locked=True).filter(pk=owner).exists():continue
                instance=candidates.select_for_update().filter(pk=pk).first()
                if not instance:continue
                reconciled+=1
                if not dry:
                    OnboardingService.reconcile(instance)
                    notify_overdue(instance)
                    instance.updated_at=timezone.now()
                    instance.save(update_fields=['updated_at'])
        if not dry:record_worker_cycle('onboarding',processed=expired+reconciled)
        self.stdout.write(f'expired={expired} reconciled={reconciled} dry_run={dry}')
