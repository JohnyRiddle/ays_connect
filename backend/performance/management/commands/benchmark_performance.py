import time
import uuid
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from accounts.models import User
from employees.models import Employee
from service_requests.models import RequestStatus, RequestType, RequestTypeSchemaVersion, Service, ServiceCategory, ServiceRequest
from work_tasks.models import Task, TaskStatus

from performance.engine import build_facts


class Command(BaseCommand):
    help = "Rollback-only PostgreSQL scale gate with 100 employees, N Tasks and N Requests."

    def add_arguments(self, parser): parser.add_argument("--size", type=int, default=10000)

    def handle(self, *args, **options):
        if connection.vendor != "postgresql": raise CommandError("PostgreSQL is required")
        size = options["size"]; now = timezone.now(); start = now - timedelta(days=1); end = now + timedelta(days=1)
        with transaction.atomic():
            user = User.objects.first()
            if not user: user = User.objects.create_superuser(username="perf-benchmark", email="perf-benchmark@example.invalid", password=uuid.uuid4().hex)
            employees = Employee.objects.bulk_create([Employee(first_name="Scale", last_name=f"Employee {index}", employee_number=f"PERF-{uuid.uuid4().hex[:16]}") for index in range(100)])
            category = ServiceCategory.objects.create(name="Performance benchmark")
            service = Service.objects.create(category=category, name="Performance benchmark")
            request_type = RequestType.objects.create(service=service, name="Performance benchmark", code=f"perf-{uuid.uuid4().hex}", created_by=employees[0])
            schema = RequestTypeSchemaVersion.objects.create(request_type=request_type, version=1, schema_json={}, created_by=employees[0])
            Task.objects.bulk_create([
                Task(number=f"PT-{uuid.uuid4().hex[:24]}", title="Scale", author=employees[index % 100], responsible_employee=employees[index % 100], executor_employee=employees[index % 100], status=TaskStatus.COMPLETED, due_at=now + timedelta(hours=1), completed_at=now, created_by=user, updated_by=user)
                for index in range(size)
            ], batch_size=1000)
            ServiceRequest.objects.bulk_create([
                ServiceRequest(number=f"PR-{uuid.uuid4().hex[:24]}", request_type=request_type, schema_version=schema, requester=employees[index % 100], created_by=user, subject="Scale", status=RequestStatus.RESOLVED, service=service, category=category, responsible_employee=employees[index % 100], assigned_employee=employees[index % 100], resolved_at=now, updated_by=user)
                for index in range(size)
            ], batch_size=1000)
            started = time.perf_counter(); fact_count = build_facts(start, end); elapsed = time.perf_counter() - started
            with connection.cursor() as cursor:
                cursor.execute("EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) SELECT value FROM performance_performancefact WHERE employee_id=%s AND metric_code='tasks_completed' AND occurred_at >= %s AND occurred_at < %s", [employees[0].pk, start, end])
                plan = "\n".join(row[0] for row in cursor.fetchall())
            self.stdout.write(f"synthetic_employees=100 tasks={size} requests={size} facts={fact_count} build_seconds={elapsed:.3f}")
            self.stdout.write(plan)
            transaction.set_rollback(True)
