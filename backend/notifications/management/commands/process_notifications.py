from django.core.management.base import BaseCommand
from notifications.services import ingest_pending,process_deliveries,reconcile_deliveries
from operations.heartbeat import record_worker_cycle
class Command(BaseCommand):
    def add_arguments(self,p):p.add_argument("--batch-size",type=int,default=100);p.add_argument("--reconcile",action="store_true")
    def handle(self,*a,**o):
        size=max(1,o["batch_size"]);recovered=reconcile_deliveries() if o["reconcile"] else 0;ingested=ingest_pending(size,o["reconcile"]);delivered=process_deliveries(size)
        record_worker_cycle("notifications",processed=ingested+delivered+recovered,metadata={"ingested":ingested,"delivered":delivered,"recovered":recovered})
        self.stdout.write(self.style.SUCCESS(f"ingested={ingested} delivered={delivered} recovered={recovered}"))
