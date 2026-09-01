from datetime import timedelta

from django.conf import settings
from django.db import connection
from django.db.models import Count
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from events.models import OutboxEvent
from notifications.models import NotificationDelivery
from performance.models import PerformanceRecalculation
from sla.models import EscalationSchedule
from access_control.services import PermissionService

from .models import WorkerHeartbeat


class SystemStatusView(APIView):
    def get(self, request):
        employee=getattr(request.user,"employee",None)
        if not request.user.is_superuser and not PermissionService.has_permission(employee=employee,permission="system.status.view"): raise PermissionDenied("System administrator access required.")
        with connection.cursor() as cursor: cursor.execute("SELECT 1")
        now = timezone.now(); threshold = now - timedelta(seconds=settings.WORKER_STALE_SECONDS)
        latest_by_name = {}
        for item in WorkerHeartbeat.objects.order_by("worker_name", "-last_seen_at"):
            latest_by_name.setdefault(item.worker_name, item)
        workers = [{
            "name": item.worker_name, "instance": item.instance_id, "status": "WORKER_OK" if item.last_seen_at >= threshold else "WORKER_STALE",
            "last_seen_at": item.last_seen_at, "last_success_at": item.last_success_at, "last_error_at": item.last_error_at,
            "last_error_code": item.last_error_code, "items_processed": item.items_processed,
        } for item in latest_by_name.values()]
        present_workers = {item["name"] for item in workers}
        workers.extend({
            "name": name, "instance": None, "status": "WORKER_UNKNOWN",
            "last_seen_at": None, "last_success_at": None, "last_error_at": None,
            "last_error_code": "", "items_processed": 0,
        } for name in settings.EXPECTED_WORKERS if name not in present_workers)
        oldest=OutboxEvent.objects.filter(status=OutboxEvent.Status.PENDING).order_by("created_at").values_list("created_at",flat=True).first()
        outbox_counts=dict(OutboxEvent.objects.values_list("status").annotate(total=Count("id")))
        outbox_counts.update({"retrying":OutboxEvent.objects.filter(status=OutboxEvent.Status.FAILED,next_attempt_at__isnull=False).count(),"terminal_failed":OutboxEvent.objects.filter(status=OutboxEvent.Status.FAILED,next_attempt_at__isnull=True).count(),"oldest_pending_age_seconds":int((now-oldest).total_seconds()) if oldest else 0})
        performance_counts=dict(PerformanceRecalculation.objects.values_list("status").annotate(total=Count("id")))
        performance_counts["stale_processing"]=PerformanceRecalculation.objects.filter(status="processing",locked_at__lt=now-timedelta(minutes=15)).count()
        return Response({
            "version": settings.AYS_CONNECT_VERSION, "generated_at":now, "database": "ok", "workers": workers,
            "queues": {
                "outbox": outbox_counts,
                "notifications": dict(NotificationDelivery.objects.values_list("status").annotate(total=Count("id"))),
                "performance": performance_counts,
                "escalations_pending": EscalationSchedule.objects.filter(status="pending").count(),
            },
        })
