from django.db import models


class WorkerHeartbeat(models.Model):
    worker_name = models.CharField(max_length=80)
    instance_id = models.CharField(max_length=120)
    last_seen_at = models.DateTimeField(db_index=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_error_at = models.DateTimeField(null=True, blank=True)
    last_error_code = models.CharField(max_length=80, blank=True)
    items_processed = models.PositiveBigIntegerField(default=0)
    metadata_safe = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("worker_name", "instance_id"), name="operations_worker_instance")]
        indexes = [models.Index(fields=("worker_name", "last_seen_at"), name="ops_worker_seen")]
