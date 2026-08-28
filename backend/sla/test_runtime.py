from datetime import datetime, time, timedelta, timezone as dt_timezone
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from service_requests.models import (RequestStatus, RequestTypeSchemaVersion,
                                     ServiceRequest)

from .models import (MetricType, PausePolicy, SLAInstance, SLAInstanceStatus,
                     SLAMetricStatus, SLAPolicyAssignmentRule,
                     SLAThresholdEvent, TimeMode)
from .runtime import (SLAInstanceService, SLAReconciliationService,
                      SLARuntimeEvaluator)
from .services import CalendarService, SLAPolicyService
from .tests import SLATestCase


class SLARuntimeTests(SLATestCase):
    def setUp(self):
        super().setUp()
        from service_requests.models import ServiceCategory,Service,RequestType
        category=ServiceCategory.objects.create(name="Runtime");self.service=Service.objects.create(category=category,name="Runtime")
        self.rt=RequestType.objects.create(service=self.service,name="Runtime",code="RUNTIME",created_by=self.actor)
        schema=RequestTypeSchemaVersion.objects.create(request_type=self.rt,version=1,schema_json={"fields":[]},created_by=self.actor);self.rt.current_schema_version=schema;self.rt.save(update_fields=["current_schema_version"])
        self.base=datetime(2026,8,31,9,tzinfo=dt_timezone.utc)
    def request(self,status=RequestStatus.NEW,submitted=None):
        return ServiceRequest.objects.create(number=f"REQ-R-{ServiceRequest.objects.count()}",request_type=self.rt,schema_version=self.rt.current_schema_version,requester=self.actor,created_by=self.user,updated_by=self.user,subject="Runtime",priority="normal",status=status,service=self.service,category=self.service.category,submitted_at=submitted or self.base)
    def published_policy(self,mode=TimeMode.ELAPSED_TIME,calendar=None,pause=PausePolicy.NONE,response=1800,resolution=28800,thresholds=None):
        policy=self.policy(calendar=calendar,mode=mode);policy.draft_response_duration_seconds=response;policy.draft_resolution_duration_seconds=resolution;policy.draft_pause_policy=pause;policy.draft_thresholds=thresholds or [{"metric_type":"response","threshold_percent":100},{"metric_type":"resolution","threshold_percent":50},{"metric_type":"resolution","threshold_percent":100}];policy.save();version=SLAPolicyService.publish(policy=policy,actor=self.actor,user=self.user);SLAPolicyAssignmentRule.objects.create(policy=policy,request_type=self.rt);return policy,version
    def test_creation_no_policy_idempotent_and_immutable_context(self):
        request=self.request();self.assertIsNone(SLAInstanceService.create_for_request(request));policy,version=self.published_policy();instance=SLAInstanceService.create_for_request(request);self.assertEqual(instance,SLAInstanceService.create_for_request(request));self.assertEqual(instance.policy_version,version);self.assertEqual(instance.metrics.count(),2);self.assertEqual(instance.resolution_cycles.count(),1)
        policy.draft_resolution_duration_seconds=1;policy.save(update_fields=["draft_resolution_duration_seconds"]);self.assertEqual(instance.metrics.get(metric_type=MetricType.RESOLUTION).duration_seconds,28800)
    def test_only_one_metric_and_elapsed_deadlines(self):
        self.published_policy(response=None,resolution=3600);instance=SLAInstanceService.create_for_request(self.request());self.assertFalse(instance.metrics.filter(metric_type=MetricType.RESPONSE).exists());self.assertEqual(instance.metrics.get().due_at,self.base+timedelta(hours=1))
    def test_response_achievement_breach_and_late_achievement(self):
        self.published_policy(response=1800,resolution=None);request=self.request();instance=SLAInstanceService.create_for_request(request);metric=instance.metrics.get();SLARuntimeEvaluator.evaluate_instance(instance,self.base+timedelta(minutes=31));metric.refresh_from_db();self.assertEqual(metric.breached_at,self.base+timedelta(minutes=30))
        request.status=RequestStatus.IN_PROGRESS;request.started_at=self.base+timedelta(minutes=40);request.save();SLAInstanceService.handle_lifecycle(request,event_at=request.started_at,previous_status=RequestStatus.ASSIGNED);metric.refresh_from_db();self.assertEqual(metric.status,SLAMetricStatus.ACHIEVED);self.assertIsNotNone(metric.breached_at)
    def test_elapsed_pause_resume_resolve_cancel_and_duplicate_pause(self):
        self.published_policy(pause=PausePolicy.WAITING_REQUESTER,response=None,resolution=3600);request=self.request();instance=SLAInstanceService.create_for_request(request)
        SLAInstanceService.pause(instance,RequestStatus.WAITING_REQUESTER,self.base+timedelta(minutes=20));SLAInstanceService.pause(instance,RequestStatus.WAITING_REQUESTER,self.base+timedelta(minutes=21));self.assertEqual(instance.pause_periods.count(),1)
        SLAInstanceService.resume(instance,self.base+timedelta(minutes=50));metric=instance.metrics.get();metric.refresh_from_db();self.assertEqual(metric.due_at,self.base+timedelta(minutes=90))
        request.status=RequestStatus.RESOLVED;request.resolved_at=self.base+timedelta(minutes=80);request.save();SLAInstanceService.handle_lifecycle(request,event_at=request.resolved_at,previous_status=RequestStatus.IN_PROGRESS);metric.refresh_from_db();self.assertEqual(metric.status,SLAMetricStatus.ACHIEVED)
    def test_business_pause_remaining_and_reopen_cycles(self):
        calendar=self.calendar(timezone="UTC");self.published_policy(mode=TimeMode.BUSINESS_TIME,calendar=calendar,pause=PausePolicy.BOTH,response=None,resolution=28800);request=self.request();instance=SLAInstanceService.create_for_request(request)
        SLAInstanceService.pause(instance,RequestStatus.WAITING_REQUESTER,self.base+timedelta(hours=3));SLAInstanceService.resume(instance,self.base+timedelta(days=1));metric=instance.metrics.get();metric.refresh_from_db();self.assertEqual(metric.due_at,self.base+timedelta(days=1,hours=5))
        request.status=RequestStatus.RESOLVED;request.resolved_at=self.base+timedelta(days=1,hours=4);request.save();SLAInstanceService.handle_lifecycle(request,event_at=request.resolved_at,previous_status=RequestStatus.IN_PROGRESS)
        request.status=RequestStatus.IN_PROGRESS;request.reopened_at=self.base+timedelta(days=2);request.save();SLAInstanceService.handle_lifecycle(request,event_at=request.reopened_at,previous_status=RequestStatus.RESOLVED);self.assertEqual(instance.resolution_cycles.count(),2);self.assertEqual(instance.metrics.filter(metric_type=MetricType.RESPONSE).count(),0)
    def test_evaluator_threshold_idempotency_and_rollback(self):
        self.published_policy(response=None,resolution=3600);instance=SLAInstanceService.create_for_request(self.request());self.assertEqual(SLARuntimeEvaluator.evaluate_instance(instance,self.base+timedelta(minutes=31)),1);self.assertEqual(SLARuntimeEvaluator.evaluate_instance(instance,self.base+timedelta(minutes=31)),0);self.assertEqual(SLAThresholdEvent.objects.count(),1)
        metric=instance.metrics.get();before=SLAThresholdEvent.objects.count()
        with patch("sla.runtime.DomainEventService.publish",side_effect=RuntimeError("outbox")):
            with self.assertRaises(RuntimeError):SLARuntimeEvaluator.evaluate_instance(instance,self.base+timedelta(hours=2))
        self.assertEqual(SLAThresholdEvent.objects.count(),before);metric.refresh_from_db();self.assertIsNone(metric.breached_at)
    def test_cancellation_reconciliation_and_api(self):
        self.published_policy();request=self.request();instance=SLAInstanceService.create_for_request(request);request.status=RequestStatus.CANCELLED;request.cancelled_at=self.base+timedelta(minutes=5);request.save();SLAInstanceService.handle_lifecycle(request,event_at=request.cancelled_at,previous_status=RequestStatus.NEW);instance.refresh_from_db();self.assertEqual(instance.status,SLAInstanceStatus.CANCELLED);self.assertFalse(instance.metrics.filter(status=SLAMetricStatus.BREACHED).exists())
        client=APIClient();client.force_authenticate(self.user);self.assertEqual(client.get(f"/api/internal/v1/requests/{request.pk}/sla/").status_code,200);self.assertEqual(client.get(f"/api/internal/v1/requests/{request.pk}/sla/history/").status_code,200)
    def test_atomic_creation(self):
        self.published_policy();request=self.request()
        with patch("sla.runtime.DomainEventService.publish",side_effect=RuntimeError("outbox")):
            with self.assertRaises(RuntimeError):SLAInstanceService.create_for_request(request)
        self.assertFalse(SLAInstance.objects.filter(request=request).exists())
