import logging

from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.utils import timezone

from service_requests.models import ServiceRequest
from sla.models import SLAInstance, SLAInstanceStatus
from sla.runtime import SLAReconciliationService, SLARuntimeEvaluator
from operations.heartbeat import record_worker_cycle

logger=logging.getLogger(__name__)


class Command(BaseCommand):
    help="Evaluate active SLA runtime instances and optionally reconcile request lifecycle."
    def add_arguments(self,parser):
        parser.add_argument("--batch-size",type=int,default=100);parser.add_argument("--reconcile",action="store_true")
    def handle(self,*args,**options):
        now=timezone.now();evaluated=events=errors=0;batch=max(1,options["batch_size"])
        if options["reconcile"]:
            for request in ServiceRequest.objects.order_by("pk").iterator(chunk_size=batch):
                try:SLAReconciliationService.reconcile_request(request);evaluated+=1
                except Exception as exc:errors+=1;logger.exception("SLA reconcile failed request=%s error=%s",request.pk,exc)
        else:
            last_pk=None
            while True:
                with transaction.atomic():
                    qs=SLAInstance.objects.filter(status__in=[SLAInstanceStatus.ACTIVE,SLAInstanceStatus.PAUSED]).order_by("pk")
                    if last_pk:qs=qs.filter(pk__gt=last_pk)
                    if connection.features.has_select_for_update_skip_locked:qs=qs.select_for_update(skip_locked=True)
                    else:qs=qs.select_for_update()
                    instances=list(qs[:batch])
                    for instance in instances:
                        try:events+=SLARuntimeEvaluator.evaluate_instance(instance,now);evaluated+=1
                        except Exception as exc:errors+=1;logger.exception("SLA evaluation failed instance=%s request=%s error=%s",instance.pk,instance.request_id,exc)
                    if instances:last_pk=instances[-1].pk
                if len(instances)<batch:break
        record_worker_cycle("sla",processed=evaluated,error_code="SLA_CYCLE_ERRORS" if errors else "",metadata={"events":events,"errors":errors})
        self.stdout.write(f"evaluated: {evaluated} events: {events} errors: {errors}")
