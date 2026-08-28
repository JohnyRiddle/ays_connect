from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone as dt_timezone

from django.db import IntegrityError, close_old_connections, connection
from django.test import TransactionTestCase, skipUnlessDBFeature

from accounts.models import User
from employees.models import Employee
from organizations.models import LegalEntity, Location, OrgUnit
from service_requests.models import (RequestTypeSchemaVersion, ServiceRequest,
                                     ServiceCategory, Service, RequestType)

from .models import (PausePolicy, SLAInstance, SLAPausePeriod, SLAPolicy,
                     SLAPolicyAssignmentRule, SLAThresholdEvent, TimeMode)
from .runtime import SLAInstanceService, SLARuntimeEvaluator
from .services import SLAPolicyService


@skipUnlessDBFeature("has_select_for_update")
class SLARuntimePostgreSQLTests(TransactionTestCase):
    reset_sequences=True
    def setUp(self):
        self.user=User.objects.create_superuser(username="sla-pg",email="sla-pg@test.local",password="x");self.actor=Employee.objects.create(user=self.user,first_name="SLA");self.le=LegalEntity.objects.create(name="PG LE");self.unit=OrgUnit.objects.create(name="PG Unit",legal_entity=self.le);self.location=Location.objects.create(name="PG Location",legal_entity=self.le)
        category=ServiceCategory.objects.create(name="PG");self.service=Service.objects.create(category=category,name="PG");self.rt=RequestType.objects.create(service=self.service,name="PG",code="PG_RUNTIME",created_by=self.actor);schema=RequestTypeSchemaVersion.objects.create(request_type=self.rt,version=1,schema_json={"fields":[]},created_by=self.actor);self.rt.current_schema_version=schema;self.rt.save(update_fields=["current_schema_version"]);self.base=datetime(2026,8,31,9,tzinfo=dt_timezone.utc)
        policy=SLAPolicy.objects.create(name="PG",code="PG_POLICY",draft_time_mode=TimeMode.ELAPSED_TIME,draft_response_duration_seconds=None,draft_resolution_duration_seconds=3600,draft_pause_policy=PausePolicy.BOTH,draft_thresholds=[{"metric_type":"resolution","threshold_percent":50},{"metric_type":"resolution","threshold_percent":100}],created_by=self.actor);SLAPolicyService.publish(policy=policy,actor=self.actor,user=self.user);SLAPolicyAssignmentRule.objects.create(policy=policy,request_type=self.rt)
        self.request=ServiceRequest.objects.create(number="REQ-PG-SLA",request_type=self.rt,schema_version=schema,requester=self.actor,created_by=self.user,updated_by=self.user,subject="PG",priority="normal",status="new",service=self.service,category=category,submitted_at=self.base)
    def _create(self):
        close_old_connections()
        try:return str(SLAInstanceService.create_for_request(ServiceRequest.objects.get(pk=self.request.pk)).pk)
        finally:connection.close()
    def test_eight_concurrent_creations_produce_one_instance(self):
        with ThreadPoolExecutor(max_workers=8) as pool:ids=list(pool.map(lambda _:self._create(),range(8)))
        self.assertEqual(len(set(ids)),1);self.assertEqual(SLAInstance.objects.filter(request=self.request).count(),1)
    def test_concurrent_evaluator_and_partial_unique_pause(self):
        instance=SLAInstanceService.create_for_request(self.request)
        def evaluate(_):
            close_old_connections()
            try:return SLARuntimeEvaluator.evaluate_instance(SLAInstance.objects.get(pk=instance.pk),self.base+timedelta(hours=2))
            finally:connection.close()
        with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(evaluate,range(4)))
        self.assertEqual(SLAThresholdEvent.objects.count(),2)
        cycle=instance.resolution_cycles.get();SLAPausePeriod.objects.create(sla_instance=instance,resolution_cycle=cycle,reason="waiting_requester",started_at=self.base)
        with self.assertRaises(IntegrityError):SLAPausePeriod.objects.create(sla_instance=instance,resolution_cycle=cycle,reason="waiting_external",started_at=self.base)
