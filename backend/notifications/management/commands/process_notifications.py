from django.core.management.base import BaseCommand
from notifications.services import ingest_pending,process_deliveries,reconcile_deliveries
class Command(BaseCommand):
    def add_arguments(self,p):p.add_argument("--batch-size",type=int,default=100);p.add_argument("--reconcile",action="store_true")
    def handle(self,*a,**o):size=max(1,o["batch_size"]);recovered=reconcile_deliveries() if o["reconcile"] else 0;self.stdout.write(self.style.SUCCESS(f"ingested={ingest_pending(size,o['reconcile'])} delivered={process_deliveries(size)} recovered={recovered}"))
