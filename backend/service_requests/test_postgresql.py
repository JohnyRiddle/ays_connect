from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.db import close_old_connections, connection, connections, transaction
from django.test import TransactionTestCase

from accounts.models import User
from audit.models import AuditEvent
from employees.models import AssignmentTarget, Employee
from events.models import OutboxEvent
from organizations.models import LegalEntity, Location, OrgUnit
from work_tasks.models import Task

from .exceptions import RequestVersionConflict
from .models import (FieldType, RequestFieldDefinition, RequestNumberSequence,
                     RequestRoutingRule, RequestType, Service,
                     ServiceCategory, ServiceRequest, ServiceRequestTask,
                     ServiceRequestWatcher, ServiceRequestComment)
from .services import (SchemaService, ServiceRequestService,
                       ServiceRequestTaskService)
from .collaboration import RequestCollaborationService


class PostgreSQLServiceRequestGateTests(TransactionTestCase):
    """Real transaction/concurrency gate; intentionally skipped outside PostgreSQL."""

    reset_sequences = True

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if connection.vendor != "postgresql":
            cls.__unittest_skip__ = True
            cls.__unittest_skip_why__ = "PostgreSQL-only integration gate"

    def setUp(self):
        self.user = User.objects.create_superuser(username="pg-gate", password="x")
        self.le = LegalEntity.objects.create(name="Gate LE")
        self.unit = OrgUnit.objects.create(name="Gate Unit", legal_entity=self.le)
        self.location = Location.objects.create(name="Gate Office", legal_entity=self.le)
        self.actor = Employee.objects.create(
            user=self.user, first_name="Gate", legal_entity=self.le,
            org_unit=self.unit, primary_location=self.location,
        )
        self.target = AssignmentTarget.objects.create(
            target_type=AssignmentTarget.Type.EMPLOYEE, employee=self.actor,
        )
        category = ServiceCategory.objects.create(name="Gate category")
        service = Service.objects.create(category=category, name="Gate service")
        self.request_type = RequestType.objects.create(
            service=service, name="Gate request", code="PG_GATE", created_by=self.actor,
        )
        RequestFieldDefinition.objects.create(
            request_type=self.request_type, key="details", label="Details",
            field_type=FieldType.TEXT, required=True,
        )
        SchemaService.publish(self.request_type, self.actor, self.user)

    @staticmethod
    def _parallel(count, worker):
        barrier = Barrier(count)
        def run(index):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return worker(index)
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=count) as executor:
            return list(executor.map(run, range(count)))

    def test_concurrent_request_numbers_are_unique_and_gap_free(self):
        RequestNumberSequence.objects.all().delete()
        def worker(index):
            with transaction.atomic():
                return ServiceRequestService._next_number()
        count=20;numbers = self._parallel(count, worker)
        self.assertEqual(len(numbers), len(set(numbers)))
        self.assertEqual(sorted(numbers), [f"REQ-{value:06d}" for value in range(1,count+1)])

    def test_concurrent_routing_creates_unique_requests_with_same_winner(self):
        RequestRoutingRule.objects.create(request_type=self.request_type, target=self.target, order=1)
        def worker(index):
            user = User.objects.get(pk=self.user.pk)
            actor = Employee.objects.get(pk=self.actor.pk)
            request_type = RequestType.objects.get(pk=self.request_type.pk)
            obj = ServiceRequestService.create(
                actor=actor, actor_user=user, request_type=request_type,
                subject=f"Concurrent {index}", payload={"details": "x"},
            )
            return obj.number, obj.assigned_employee_id
        results = self._parallel(6, worker)
        self.assertEqual(len({number for number, _ in results}), 6)
        self.assertEqual({employee for _, employee in results}, {self.actor.pk})

    def test_concurrent_assignment_rejects_stale_writer(self):
        obj = ServiceRequestService.create(
            actor=self.actor, actor_user=self.user, request_type=self.request_type,
            subject="Assign race", payload={"details": "x"},
        )
        def worker(index):
            user = User.objects.get(pk=self.user.pk)
            actor = Employee.objects.get(pk=self.actor.pk)
            target = AssignmentTarget.objects.get(pk=self.target.pk)
            request = ServiceRequest.objects.get(pk=obj.pk)
            try:
                ServiceRequestService.assign(
                    request=request, actor=actor, actor_user=user, version=1,
                    target=target, reason=f"worker {index}",
                )
                return "ok"
            except RequestVersionConflict:
                return "conflict"
        self.assertCountEqual(self._parallel(2, worker), ["ok", "conflict"])
        obj.refresh_from_db()
        self.assertEqual(obj.version, 2)
        self.assertEqual(obj.assignment_history.count(), 1)

    def test_request_task_rolls_back_when_audit_fails(self):
        obj = ServiceRequestService.create(
            actor=self.actor, actor_user=self.user, request_type=self.request_type,
            subject="Atomic audit", payload={"details": "x"},
        )
        baseline = (Task.objects.count(), ServiceRequestTask.objects.count(), OutboxEvent.objects.count())
        with patch("service_requests.services.AuditService.record", side_effect=RuntimeError("audit unavailable")):
            with self.assertRaises(RuntimeError):
                ServiceRequestTaskService.create_task(
                    request=obj, actor=self.actor, actor_user=self.user, version=1,
                    title="Must rollback", responsible_target=self.target,
                )
        self.assertEqual((Task.objects.count(), ServiceRequestTask.objects.count(), OutboxEvent.objects.count()), baseline)

    def test_request_task_rolls_back_when_outbox_fails(self):
        obj = ServiceRequestService.create(
            actor=self.actor, actor_user=self.user, request_type=self.request_type,
            subject="Atomic outbox", payload={"details": "x"},
        )
        baseline = (Task.objects.count(), ServiceRequestTask.objects.count(), AuditEvent.objects.count())
        with patch("service_requests.services.DomainEventService.publish", side_effect=RuntimeError("outbox unavailable")):
            with self.assertRaises(RuntimeError):
                ServiceRequestTaskService.create_task(
                    request=obj, actor=self.actor, actor_user=self.user, version=1,
                    title="Must rollback", responsible_target=self.target,
                )
        self.assertEqual((Task.objects.count(), ServiceRequestTask.objects.count(), AuditEvent.objects.count()), baseline)

    def test_concurrent_watcher_add_keeps_one_active_record(self):
        obj=ServiceRequestService.create(actor=self.actor,actor_user=self.user,request_type=self.request_type,subject="Watcher race",payload={"details":"x"})
        def worker(index):
            user=User.objects.get(pk=self.user.pk);actor=Employee.objects.get(pk=self.actor.pk);request=ServiceRequest.objects.get(pk=obj.pk)
            return str(RequestCollaborationService.add_watcher(request=request,employee=actor,actor=actor,actor_user=user).pk)
        ids=self._parallel(2,worker);self.assertEqual(len(set(ids)),1);self.assertEqual(ServiceRequestWatcher.objects.filter(request=obj,employee=self.actor,removed_at__isnull=True).count(),1)

    def test_concurrent_comments_do_not_change_request_version(self):
        obj=ServiceRequestService.create(actor=self.actor,actor_user=self.user,request_type=self.request_type,subject="Comment race",payload={"details":"x"});version=obj.version
        def worker(index):
            user=User.objects.get(pk=self.user.pk);actor=Employee.objects.get(pk=self.actor.pk);request=ServiceRequest.objects.get(pk=obj.pk)
            return str(RequestCollaborationService.add_comment(request=request,actor=actor,actor_user=user,body=f"Comment {index}").pk)
        ids=self._parallel(4,worker);obj.refresh_from_db();self.assertEqual(len(set(ids)),4);self.assertEqual(ServiceRequestComment.objects.filter(request=obj).count(),4);self.assertEqual(obj.version,version)
