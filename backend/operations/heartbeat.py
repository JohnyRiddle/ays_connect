import os
import socket
import uuid

from django.utils import timezone
from django.db import models

from .models import WorkerHeartbeat


def instance_id(): return os.getenv("WORKER_INSTANCE_ID") or socket.gethostname()


def record_worker_cycle(worker_name, *, processed=0, error_code="", metadata=None):
    now = timezone.now(); failed = bool(error_code)
    safe_metadata = dict(metadata or {})
    safe_metadata["run_id"] = str(uuid.uuid4())
    defaults = {"last_seen_at": now, "metadata_safe": safe_metadata, "last_error_code": error_code[:80]}
    if failed: defaults["last_error_at"] = now
    else: defaults["last_success_at"] = now
    heartbeat, _ = WorkerHeartbeat.objects.update_or_create(worker_name=worker_name, instance_id=instance_id(), defaults=defaults)
    if processed:
        WorkerHeartbeat.objects.filter(pk=heartbeat.pk).update(items_processed=models.F("items_processed") + max(0, int(processed)))
