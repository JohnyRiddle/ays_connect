from django.test import TestCase
from accounts.models import User
from employees.models import Employee, AssignmentTarget
from organizations.models import LegalEntity, OrgUnit, Location
from work_tasks.models import TaskStatus
from .exceptions import RequestBusinessError, RequestInvalidTransition, RequestVersionConflict
from .models import ServiceCategory, Service, RequestType, RequestFieldDefinition, FieldType, RequestRoutingRule, RequestStatus, ServiceRequestTask
from .services import SchemaService, ServiceRequestService, ServiceRequestTaskService
from .state_machine import ServiceRequestStateMachine

class ServiceRequestCoreTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_superuser(username="request-admin",password="x")
        self.le=LegalEntity.objects.create(name="LE");self.unit=OrgUnit.objects.create(name="Unit",legal_entity=self.le);self.location=Location.objects.create(name="Office",legal_entity=self.le)
        self.actor=Employee.objects.create(user=self.user,first_name="Actor",legal_entity=self.le,org_unit=self.unit,primary_location=self.location)
        self.target=AssignmentTarget.objects.create(target_type=AssignmentTarget.Type.EMPLOYEE,employee=self.actor)
        category=ServiceCategory.objects.create(name="IT");service=Service.objects.create(category=category,name="Support")
        self.rt=RequestType.objects.create(service=service,name="Help",code="HELP",created_by=self.actor)
        RequestFieldDefinition.objects.create(request_type=self.rt,key="details",label="Details",field_type=FieldType.TEXT,required=True)
        SchemaService.publish(self.rt,self.actor,self.user)
    def create(self,routed=False):
        if routed:RequestRoutingRule.objects.create(request_type=self.rt,target=self.target,order=1)
        return ServiceRequestService.create(actor=self.actor,actor_user=self.user,request_type=self.rt,subject="Need help",payload={"details":"broken"})
    def test_create_snapshots_schema_values_number_and_route(self):
        obj=self.create(True);self.assertEqual(obj.number,"REQ-000001");self.assertEqual(obj.status,RequestStatus.ASSIGNED);self.assertEqual(obj.assigned_employee,self.actor);self.assertEqual(obj.field_values.get().label,"Details")
        field=self.rt.fields.get();field.label="Renamed";field.save();self.assertEqual(obj.field_values.get().label,"Details")
    def test_state_machine_and_optimistic_locking(self):
        obj=self.create(True);obj=ServiceRequestService.start(request=obj,actor=self.actor,actor_user=self.user,version=1,reason="")
        with self.assertRaises(RequestVersionConflict):ServiceRequestService.cancel(request=obj,actor=self.actor,actor_user=self.user,version=1,reason="cancel")
        with self.assertRaises(RequestInvalidTransition):ServiceRequestStateMachine.validate(RequestStatus.NEW,RequestStatus.RESOLVED)
    def test_dynamic_update_is_versioned_and_locked_after_start(self):
        obj=self.create(True);obj=ServiceRequestService.update(request=obj,actor=self.actor,actor_user=self.user,version=1,payload={"details":"updated"})
        self.assertEqual(obj.field_values.get().value_json,"updated");self.assertEqual(obj.field_revisions.count(),1)
        obj=ServiceRequestService.start(request=obj,actor=self.actor,actor_user=self.user,version=2,reason="")
        with self.assertRaises(RequestBusinessError):ServiceRequestService.update(request=obj,actor=self.actor,actor_user=self.user,version=3,payload={"details":"late"})
    def test_wait_resume_resolve_close_and_reopen(self):
        obj=self.create(True);obj=ServiceRequestService.start(request=obj,actor=self.actor,actor_user=self.user,version=1,reason="")
        obj=ServiceRequestService.wait(request=obj,actor=self.actor,actor_user=self.user,version=2,waiting_type=RequestStatus.WAITING_REQUESTER,comment="Need info")
        obj=ServiceRequestService.resume(request=obj,actor=self.actor,actor_user=self.user,version=3,reason="received");self.assertIsNotNone(obj.waiting_periods.get().ended_at)
        obj=ServiceRequestService.resolve(request=obj,actor=self.actor,actor_user=self.user,version=4,resolution_code="DONE",resolution_comment="Fixed")
        obj=ServiceRequestService.close(request=obj,actor=self.actor,actor_user=self.user,version=5,reason="confirmed")
        obj=ServiceRequestService.reopen(request=obj,actor=self.actor,actor_user=self.user,version=6,reason="recurrence");self.assertEqual(obj.status,RequestStatus.IN_PROGRESS)
    def test_create_task_and_completion_policy(self):
        obj=self.create(True);obj=ServiceRequestService.start(request=obj,actor=self.actor,actor_user=self.user,version=1,reason="")
        task=ServiceRequestTaskService.create_task(request=obj,actor=self.actor,actor_user=self.user,version=2,title="Execute",responsible_target=self.target)
        self.assertEqual(task.source_id,str(obj.pk));self.assertEqual(task.source_type,"request");self.assertTrue(ServiceRequestTask.objects.filter(request=obj,task=task).exists())
        self.rt.task_completion_policy=RequestType.TaskCompletionPolicy.ALL_COMPLETED;self.rt.save(update_fields=["task_completion_policy"]);obj.refresh_from_db()
        with self.assertRaises(RequestBusinessError):ServiceRequestService.resolve(request=obj,actor=self.actor,actor_user=self.user,version=3,resolution_code="DONE",resolution_comment="Fixed")
