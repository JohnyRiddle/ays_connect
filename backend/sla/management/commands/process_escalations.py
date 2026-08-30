import logging

from django.core.management.base import BaseCommand
from django.db import connection,transaction
from django.utils import timezone

from sla.escalation import (EscalationReconciliationService,
                            EscalationRuntimeService)
from sla.models import EscalationInstance,EscalationInstanceStatus,SLAInstance

logger=logging.getLogger(__name__)
class Command(BaseCommand):
    help="Process escalation rules and delayed schedules."
    def add_arguments(self,parser):parser.add_argument("--batch-size",type=int,default=100);parser.add_argument("--reconcile",action="store_true")
    def handle(self,*args,**options):
        now=timezone.now();scanned=actions=errors=0;batch=max(1,options["batch_size"]);last_pk=None
        model=SLAInstance if options["reconcile"] else EscalationInstance
        while True:
            with transaction.atomic():
                qs=model.objects.order_by("pk")
                if not options["reconcile"]:qs=qs.filter(status=EscalationInstanceStatus.ACTIVE)
                if last_pk:qs=qs.filter(pk__gt=last_pk)
                qs=qs.select_for_update(skip_locked=True) if connection.features.has_select_for_update_skip_locked else qs.select_for_update();item_ids=list(qs.values_list("pk",flat=True)[:batch])
                if item_ids:last_pk=item_ids[-1]
            for item_id in item_ids:
                try:
                    item=model.objects.get(pk=item_id);instance=EscalationReconciliationService.reconcile_sla(item,now) if options["reconcile"] else item
                    if instance and not options["reconcile"]:actions+=EscalationRuntimeService.process_instance(instance,now)
                    scanned+=1
                except Exception as exc:errors+=1;logger.exception("Escalation processing failed instance=%s error=%s",item_id,exc)
            if len(item_ids)<batch:break
        self.stdout.write(f"instances_scanned: {scanned} actions: {actions} errors: {errors}")
