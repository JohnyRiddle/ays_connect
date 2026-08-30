from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from employees.models import AssignmentTarget,Employee
from events.models import OutboxEvent
from service_requests.models import RequestStatus,ServiceRequestWatcher
from notifications.models import Notification
from notifications.services import ingest_pending,process_deliveries

from .escalation import (EscalationInstanceService,EscalationPolicyService,
                         EscalationReconciliationService,
                         EscalationRuntimeService)
from .exceptions import SLAError
from .models import (EscalationActionDefinition,EscalationActionType,
                     EscalationExecution,EscalationExecutionStatus,
                     EscalationInstance,EscalationPolicy,EscalationRule,
                     EscalationScheduleStatus,EscalationTargetType,
                     EscalationTrigger,MetricType,PausePolicy,
                     SLAEscalationBinding,TimeMode)
from .runtime import SLAInstanceService,SLARuntimeEvaluator
from .test_runtime import SLARuntimeTests


class EscalationTests(SLARuntimeTests):
    def escalation_policy(self,rules):
        policy=EscalationPolicy.objects.create(name="Escalation",code=f"ESC_{EscalationPolicy.objects.count()}",created_by=self.actor)
        for rule_data,actions in rules:
            rule=EscalationRule.objects.create(policy=policy,**rule_data)
            for action in actions:EscalationActionDefinition.objects.create(rule=rule,**action)
        return policy
    def bind(self,sla_version,policy):
        version=EscalationPolicyService.publish(policy,self.actor,self.user);SLAEscalationBinding.objects.create(sla_policy_version=sla_version,escalation_policy_version=version,created_by=self.actor);return version
    def test_policy_validation_versioning_and_immutability(self):
        empty=self.escalation_policy([])
        with self.assertRaises(SLAError):EscalationPolicyService.publish(empty,self.actor,self.user)
        policy=self.escalation_policy([({"name":"Warning","trigger_type":"on_warning","metric_type":"resolution","threshold_percent":80,"level":1},[{"action_type":"request_notification","target_type":"request_requester"}])]);v1=EscalationPolicyService.publish(policy,self.actor,self.user);rule=policy.draft_rules.first();rule.threshold_percent=70;rule.save();v2=EscalationPolicyService.publish(policy,self.actor,self.user);self.assertEqual(v1.rules_snapshot[0]["threshold_percent"],80);self.assertEqual(v2.rules_snapshot[0]["threshold_percent"],70)
        v1.rules_snapshot=[]
        with self.assertRaises(ValidationError):v1.save()
    def test_invalid_rule_and_actions(self):
        invalid=self.escalation_policy([({"name":"Bad","trigger_type":"on_warning","metric_type":"resolution","threshold_percent":100},[{"action_type":"request_notification"}])])
        with self.assertRaises(SLAError):EscalationPolicyService.publish(invalid,self.actor,self.user)
        invalid2=self.escalation_policy([({"name":"Delay","trigger_type":"after_breach_duration","metric_type":"resolution","delay_seconds":0},[{"action_type":"change_priority","action_config":{"target_priority":"invalid"}}])])
        with self.assertRaises(SLAError):EscalationPolicyService.publish(invalid2,self.actor,self.user)
    def test_no_binding_and_idempotent_instance(self):
        _,sla_version=self.published_policy(response=None,resolution=3600);sla=SLAInstanceService.create_for_request(self.request());self.assertIsNone(EscalationInstanceService.create_for_sla(sla));policy=self.escalation_policy([({"name":"Breach","trigger_type":"on_breach","metric_type":"resolution"},[{"action_type":"request_notification","target_type":"request_requester"}])]);self.bind(sla_version,policy);instance=EscalationInstanceService.create_for_sla(sla);self.assertEqual(instance,EscalationInstanceService.create_for_sla(sla))
    def test_warning_breach_delayed_actions_and_api(self):
        manager_user=User.objects.create_user(username="manager");manager=Employee.objects.create(user=manager_user,first_name="Manager");self.actor.manager=manager;self.actor.save(update_fields=["manager"])
        _,sla_version=self.published_policy(response=None,resolution=3600,thresholds=[{"metric_type":"resolution","threshold_percent":50},{"metric_type":"resolution","threshold_percent":100}]);policy=self.escalation_policy([
            ({"name":"Warn","trigger_type":"on_warning","metric_type":"resolution","threshold_percent":50,"level":1},[{"action_type":"request_notification","target_type":"request_requester"}]),
            ({"name":"Breach","trigger_type":"on_breach","metric_type":"resolution","level":2},[{"action_type":"add_watcher","target_type":"request_executor_manager"}]),
            ({"name":"Delay","trigger_type":"after_breach_duration","metric_type":"resolution","delay_seconds":1800,"level":3},[{"action_type":"change_priority","action_config":{"target_priority":"high"}}]),
        ]);self.bind(sla_version,policy);request=self.request();request.assigned_employee=self.actor;request.responsible_employee=self.actor;request.save();sla=SLAInstanceService.create_for_request(request);instance=sla.escalation_instance
        SLARuntimeEvaluator.evaluate_instance(sla,self.base+timedelta(minutes=31));EscalationRuntimeService.process_instance(instance,self.base+timedelta(minutes=31));self.assertEqual(OutboxEvent.objects.filter(event_type="notification.requested").count(),1)
        ingest_pending();process_deliveries();inbox=Notification.objects.get(recipient=self.user);self.assertEqual(inbox.entity_id,str(request.pk));self.assertIsNotNone(inbox.delivered_at)
        SLARuntimeEvaluator.evaluate_instance(sla,self.base+timedelta(minutes=61));EscalationRuntimeService.process_instance(instance,self.base+timedelta(minutes=61));self.assertTrue(ServiceRequestWatcher.objects.filter(request=request,employee=manager,removed_at__isnull=True).exists());self.assertEqual(instance.schedules.get().status,EscalationScheduleStatus.PENDING)
        EscalationRuntimeService.process_instance(instance,self.base+timedelta(minutes=92));request.refresh_from_db();self.assertEqual(request.priority,"high");self.assertEqual(instance.executions.count(),3);self.assertTrue(instance.executions.filter(triggered_at=self.base+timedelta(minutes=90)).exists())
        client=APIClient();client.force_authenticate(self.user);self.assertEqual(client.get(f"/api/internal/v1/requests/{request.pk}/escalations/").status_code,200);self.assertEqual(client.get(f"/api/internal/v1/requests/{request.pk}/escalations/history/").status_code,200)
    def test_priority_downgrade_reassign_and_missing_manager_skip(self):
        target=AssignmentTarget.objects.create(target_type="employee",employee=self.actor);_,sla_version=self.published_policy(response=None,resolution=60);policy=self.escalation_policy([({"name":"Breach","trigger_type":"on_breach","metric_type":"resolution"},[{"action_type":"change_priority","action_config":{"target_priority":"high"}},{"action_type":"reassign","assignment_target":target},{"action_type":"request_notification","target_type":"request_executor_manager"}])]);self.bind(sla_version,policy);request=self.request();request.priority="critical";request.save();sla=SLAInstanceService.create_for_request(request);SLARuntimeEvaluator.evaluate_instance(sla,self.base+timedelta(minutes=2));EscalationRuntimeService.process_instance(sla.escalation_instance,self.base+timedelta(minutes=2));request.refresh_from_db();self.assertEqual(request.priority,"critical");self.assertEqual(request.assigned_employee,self.actor);self.assertEqual(sla.escalation_instance.executions.filter(status="skipped").count(),2)
    def test_delayed_cancel_and_atomic_outbox(self):
        _,sla_version=self.published_policy(response=None,resolution=60);policy=self.escalation_policy([({"name":"Delay","trigger_type":"after_breach_duration","metric_type":"resolution","delay_seconds":60},[{"action_type":"request_notification","target_type":"request_requester"}])]);self.bind(sla_version,policy);request=self.request();sla=SLAInstanceService.create_for_request(request);SLARuntimeEvaluator.evaluate_instance(sla,self.base+timedelta(minutes=1));instance=sla.escalation_instance;EscalationRuntimeService.process_instance(instance,self.base+timedelta(minutes=1));metric=sla.metrics.get();metric.achieved_at=self.base+timedelta(seconds=90);metric.save();EscalationRuntimeService.process_instance(instance,self.base+timedelta(minutes=2));self.assertEqual(instance.schedules.get().status,EscalationScheduleStatus.CANCELLED);self.assertEqual(instance.executions.count(),0)
        metric.achieved_at=None;metric.save();instance.schedules.all().delete()
        with patch("sla.escalation.DomainEventService.publish",side_effect=RuntimeError("outbox")):
            with self.assertRaises(RuntimeError):EscalationRuntimeService.process_instance(instance,self.base+timedelta(minutes=4))
        self.assertEqual(instance.executions.count(),0)
