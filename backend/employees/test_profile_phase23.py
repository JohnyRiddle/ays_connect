import base64
import tempfile
from concurrent.futures import ThreadPoolExecutor

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections, connections
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework.test import APIClient

from access_control.models import EmployeeRole, Permission, Role, RolePermission, Scope
from audit.models import AuditEvent
from events.models import OutboxEvent
from .models import Employee, EmployeeDataChangeRequest, EmployeeProfile
from .profile_services import ChangeRequestService, ProfileService, can_see, completeness, ensure_profile


def employee(email):
    user=get_user_model().objects.create_user(username=email,email=email,password="Safe-password-123")
    return user,Employee.objects.create(user=user,first_name="Иван",last_name="Тестов",work_email=email)


class EmployeeProfilePhase23Tests(TestCase):
    def setUp(self):self.user,self.employee=employee("self@example.test");self.profile=ensure_profile(self.employee,self.user)
    def test_profile_creation_is_audited_and_outboxed(self):
        self.assertTrue(AuditEvent.objects.filter(action="people.profile.created").exists());self.assertTrue(OutboxEvent.objects.filter(event_type="people.profile.created").exists())
    def test_profile_update_and_optimistic_lock(self):
        item=ProfileService.update(self.employee,self.user,1,{"bio":"О себе"});self.assertEqual(item.version,2)
        with self.assertRaises(ValidationError):ProfileService.update(self.employee,self.user,1,{"bio":"Устарело"})
    def test_visibility_is_typed(self):
        with self.assertRaises(ValidationError):ProfileService.visibility(self.employee,self.user,1,{"bio_visibility":"world"})
    def test_completeness_is_computed(self):
        value=completeness(self.employee,self.profile);self.assertIn("percentage",value);self.assertIn("missing_fields",value)
    def test_change_request_lifecycle(self):
        reviewer,_=employee("hr@example.test");item=ChangeRequestService.submit(self.employee,self.user,"work_phone",{"value":"+7 913 000-00-00"},"Новый номер")
        item=ChangeRequestService.transition(item,reviewer,1,"approved");item=ChangeRequestService.apply(item,reviewer,2);self.employee.refresh_from_db();self.assertEqual(item.status,"applied");self.assertEqual(self.employee.work_phone,"+7 913 000-00-00")
    def test_self_approval_forbidden(self):
        item=ChangeRequestService.submit(self.employee,self.user,"work_email",{"value":"new@example.test"},"Новая почта")
        with self.assertRaises(ValidationError):ChangeRequestService.transition(item,self.user,1,"approved")
    def test_stale_snapshot_blocks_apply(self):
        reviewer,_=employee("review@example.test");item=ChangeRequestService.submit(self.employee,self.user,"work_phone",{"value":"+79990000000"},"Номер");item=ChangeRequestService.transition(item,reviewer,1,"approved");self.employee.work_phone="+78880000000";self.employee.save()
        item=ChangeRequestService.apply(item,reviewer,2);self.assertEqual(item.status,"failed");self.assertEqual(item.review_comment,"stale_snapshot")
    def test_cancel_does_not_change_employee(self):
        item=ChangeRequestService.submit(self.employee,self.user,"work_email",{"value":"changed@example.test"},"Почта");ChangeRequestService.cancel(item,self.user,1);self.employee.refresh_from_db();self.assertEqual(self.employee.work_email,"self@example.test")
    def test_sensitive_values_are_not_in_events(self):
        ChangeRequestService.submit(self.employee,self.user,"work_email",{"value":"secret@example.test"},"Почта")
        event=OutboxEvent.objects.filter(event_type="people.data_change_request.submitted").latest("created_at");self.assertNotIn("secret@example.test",str(event.payload))
    def test_private_visibility_denies_colleague(self):
        other,_=employee("other@example.test");self.assertFalse(can_see(self.profile,"additional_email",other,self.employee))
    def test_invalid_avatar_is_rejected(self):
        with self.assertRaises(ValidationError):ProfileService.avatar(self.employee,self.user,SimpleUploadedFile("x.svg",b"<svg/>",content_type="image/svg+xml"))
    def test_avatar_metadata_rolls_back_with_outbox(self):
        png=base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")
        with tempfile.TemporaryDirectory() as media,override_settings(MEDIA_ROOT=media):
            from unittest.mock import patch
            with patch("employees.profile_services.DomainEventService.publish",side_effect=RuntimeError("outbox")),self.assertRaises(RuntimeError):ProfileService.avatar(self.employee,self.user,SimpleUploadedFile("x.png",png,content_type="image/png"))
            self.employee.refresh_from_db();self.assertFalse(self.employee.avatar)


class EmployeeProfileSecurityApiTests(TestCase):
    def setUp(self):
        self.user,self.employee=employee("api-self@example.test");self.other_user,self.other=employee("api-other@example.test")
        self.client=APIClient();self.client.force_authenticate(self.user)
        permission=Permission.objects.get(code="people.directory.view");role=Role.objects.create(code="directory-own",name="Directory own");RolePermission.objects.create(role=role,permission=permission,scope=Scope.OWN);EmployeeRole.objects.create(employee=self.employee,role=role)
    def test_self_endpoint_never_accepts_foreign_employee_id(self):
        response=self.client.patch("/api/internal/v1/people/me/",{"version":1,"employee_id":str(self.other.pk),"bio":"x"},format="json")
        self.assertEqual(response.status_code,400);self.assertFalse(EmployeeProfile.objects.filter(employee=self.other,bio="x").exists())
    def test_directory_detail_is_idor_protected(self):
        response=self.client.get(f"/api/internal/v1/people/directory/{self.other.pk}/")
        self.assertEqual(response.status_code,404)
    def test_private_field_is_masked_in_directory(self):
        permission=Permission.objects.get(code="people.directory.view");role=Role.objects.create(code="directory-global",name="Directory global");RolePermission.objects.create(role=role,permission=permission,scope=Scope.GLOBAL);EmployeeRole.objects.create(employee=self.employee,role=role)
        profile=ensure_profile(self.other,self.other_user);profile.additional_email="private@example.test";profile.save();response=self.client.get(f"/api/internal/v1/people/directory/{self.other.pk}/")
        self.assertEqual(response.status_code,200);self.assertIsNone(response.data["additional_email"])
    def test_inactive_employee_cannot_use_self_service(self):
        self.employee.is_active=False;self.employee.save(update_fields=["is_active"]);response=self.client.get("/api/internal/v1/people/me/");self.assertEqual(response.status_code,403)
    def test_change_request_is_always_created_for_actor(self):
        response=self.client.post("/api/internal/v1/people/me/change-requests/",{"employee":str(self.other.pk),"field_type":"work_phone","requested_value":{"value":"+79990000000"},"reason":"Номер"},format="json")
        self.assertEqual(response.status_code,201);self.assertEqual(EmployeeDataChangeRequest.objects.get(pk=response.data["id"]).employee,self.employee)


class EmployeeProfileConcurrencyTests(TransactionTestCase):
    reset_sequences=True
    def setUp(self):self.user,self.employee=employee("race@example.test");ensure_profile(self.employee,self.user)
    def _update(self,version,value):
        close_old_connections()
        try:ProfileService.update(Employee.objects.get(pk=self.employee.pk),get_user_model().objects.get(pk=self.user.pk),version,{"bio":value});return "ok"
        except Exception:return "conflict"
        finally:connections.close_all()
    def test_concurrent_profile_update_has_one_winner(self):
        with ThreadPoolExecutor(max_workers=2) as pool:result=list(pool.map(lambda x:self._update(1,x),["A","B"]))
        self.assertEqual(result.count("ok"),1)
    def test_concurrent_apply_is_idempotent(self):
        reviewer,_=employee("race-review@example.test");item=ChangeRequestService.submit(self.employee,self.user,"work_phone",{"value":"+79990000000"},"Номер");item=ChangeRequestService.transition(item,reviewer,1,"approved")
        def run(_):
            close_old_connections()
            try:ChangeRequestService.apply(EmployeeDataChangeRequest.objects.get(pk=item.pk),get_user_model().objects.get(pk=reviewer.pk),2);return "ok"
            except Exception:return "conflict"
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:result=list(pool.map(run,[1,2]))
        self.assertGreaterEqual(result.count("ok"),1);self.assertEqual(EmployeeDataChangeRequest.objects.get(pk=item.pk).status,"applied")
    def _transition(self,item_id,reviewer_id,target,version=1):
        close_old_connections()
        try:ChangeRequestService.transition(EmployeeDataChangeRequest.objects.get(pk=item_id),get_user_model().objects.get(pk=reviewer_id),version,target);return "ok"
        except Exception:return "conflict"
        finally:connections.close_all()
    def test_concurrent_visibility_update_has_one_winner(self):
        def run(value):
            close_old_connections()
            try:ProfileService.visibility(Employee.objects.get(pk=self.employee.pk),get_user_model().objects.get(pk=self.user.pk),1,{"bio_visibility":value});return "ok"
            except Exception:return "conflict"
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:result=list(pool.map(run,["team","organization"]))
        self.assertEqual(result.count("ok"),1)
    def test_concurrent_profile_and_visibility_share_version(self):
        def visible(_):
            close_old_connections()
            try:ProfileService.visibility(Employee.objects.get(pk=self.employee.pk),get_user_model().objects.get(pk=self.user.pk),1,{"bio_visibility":"team"});return "ok"
            except Exception:return "conflict"
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:result=[pool.submit(self._update,1,"bio"),pool.submit(visible,1)];result=[x.result() for x in result]
        self.assertEqual(result.count("ok"),1)
    def test_duplicate_approval_has_one_winner(self):
        reviewer,_=employee("approve@example.test");item=ChangeRequestService.submit(self.employee,self.user,"work_phone",{"value":"+79990000001"},"Номер")
        with ThreadPoolExecutor(max_workers=2) as pool:result=list(pool.map(lambda _:self._transition(item.pk,reviewer.pk,"approved"),[1,2]))
        self.assertEqual(result.count("ok"),1)
    def test_approve_reject_race_has_one_terminal_result(self):
        reviewer,_=employee("decision@example.test");item=ChangeRequestService.submit(self.employee,self.user,"work_phone",{"value":"+79990000002"},"Номер")
        with ThreadPoolExecutor(max_workers=2) as pool:result=[pool.submit(self._transition,item.pk,reviewer.pk,target) for target in ("approved","rejected")];result=[x.result() for x in result]
        self.assertEqual(result.count("ok"),1);self.assertIn(EmployeeDataChangeRequest.objects.get(pk=item.pk).status,{"approved","rejected"})
    def test_cancel_approval_race_has_one_terminal_result(self):
        reviewer,_=employee("cancel-approve@example.test");item=ChangeRequestService.submit(self.employee,self.user,"work_phone",{"value":"+79990000003"},"Номер")
        def cancel():
            close_old_connections()
            try:ChangeRequestService.cancel(EmployeeDataChangeRequest.objects.get(pk=item.pk),get_user_model().objects.get(pk=self.user.pk),1);return "ok"
            except Exception:return "conflict"
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:a=pool.submit(cancel);b=pool.submit(self._transition,item.pk,reviewer.pk,"approved");result=[a.result(),b.result()]
        self.assertEqual(result.count("ok"),1)
    def test_duplicate_cancel_has_one_winner(self):
        item=ChangeRequestService.submit(self.employee,self.user,"work_phone",{"value":"+79990000004"},"Номер")
        def run(_):
            close_old_connections()
            try:ChangeRequestService.cancel(EmployeeDataChangeRequest.objects.get(pk=item.pk),get_user_model().objects.get(pk=self.user.pk),1);return "ok"
            except Exception:return "conflict"
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:result=list(pool.map(run,[1,2]))
        self.assertEqual(result.count("ok"),1)
    def test_apply_reject_race_preserves_approved_lifecycle(self):
        reviewer,_=employee("apply-reject@example.test");item=ChangeRequestService.submit(self.employee,self.user,"work_phone",{"value":"+79990000005"},"Номер");item=ChangeRequestService.transition(item,reviewer,1,"approved")
        def apply(_):
            close_old_connections()
            try:ChangeRequestService.apply(EmployeeDataChangeRequest.objects.get(pk=item.pk),get_user_model().objects.get(pk=reviewer.pk),2);return "ok"
            except Exception:return "conflict"
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:result=[pool.submit(apply,1),pool.submit(self._transition,item.pk,reviewer.pk,"rejected",2)];result=[x.result() for x in result]
        self.assertEqual(result.count("ok"),1);self.assertEqual(EmployeeDataChangeRequest.objects.get(pk=item.pk).status,"applied")
    def test_concurrent_submissions_keep_distinct_snapshots(self):
        def run(value):
            close_old_connections()
            try:return str(ChangeRequestService.submit(Employee.objects.get(pk=self.employee.pk),get_user_model().objects.get(pk=self.user.pk),"work_phone",{"value":value},"Номер").pk)
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:result=list(pool.map(run,["+79990000006","+79990000007"]))
        self.assertEqual(len(set(result)),2)
