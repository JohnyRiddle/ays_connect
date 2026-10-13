import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest.mock import Mock

from django.db import IntegrityError, close_old_connections, connection, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIClient

from accounts.models import User
from access_control.models import EmployeeRole, Permission, Role, RolePermission
from audit.models import AuditEvent
from events.models import OutboxEvent
from notifications.channels import ProviderFailure, ProviderResult
from organizations.models import Location
from organizations.object_services import ObjectService
from .models import AssignmentTarget, Employee, EmployeeAssignment, EmployeeInvitation, RegistrationRequest
from .onboarding import InvitationService
from .registration import ObjectInvitationService as Invite, ObjectRegistrationService as Register, ResponsibilityService, public_locations
from .registration_mail import process_mail
from .services import EmployeeService

PASSWORD = "Synthetic-Register-2026!"
PUBLIC = "/api/public/v1/registration/"
ADMIN = "/api/internal/v1/registration/"


class Setup:
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.owner = User.objects.create_superuser(username="registration-owner", email="owner@synthetic.test", password=PASSWORD)
        Employee.objects.create(user=self.owner, first_name="Owner")
        self.location = self.new_object("Main")
        self.other = self.new_object("Other")
        self.role = Role.objects.create(code="registration-test-viewer", name="Viewer")
        for code, scope in [("location.view", "location"), ("people.profile.view_self", "own")]:
            permission, _ = Permission.objects.get_or_create(code=code, defaults={"name": code})
            RolePermission.objects.create(role=self.role, permission=permission, scope=scope)
        self.plan = {"role": str(self.role.pk), "access_locations": [str(self.location.pk)], "responsibility_mode": "selected", "responsibility_locations": []}
        self.client = APIClient()

    def new_object(self, name):
        return ObjectService.create(user=self.owner, key=str(uuid.uuid4()), data={"name": name, "business_type": "office", "timezone": "Asia/Novosibirsk"})[0]

    def payload(self, **kwargs):
        return {"email": "new@synthetic.test", "first_name": "Имя", "last_name": "Фамилия", "middle_name": "", "password": PASSWORD, "password_confirmation": PASSWORD, "location": self.location, **kwargs}

    def submit(self, **kwargs):
        return Register.submit(**self.payload(**kwargs))

    def approve(self, item, **kwargs):
        return Register.approve(registration=item, actor=self.owner, plan=self.plan, **kwargs)


@override_settings(SECURE_SSL_REDIRECT=False, NOTIFICATIONS_EMAIL_ENABLED=True)
class RegistrationTests(Setup, TestCase):
    def test_self_registration_direct_pending_then_approval_has_no_early_user_or_employee(self):
        item, token = self.submit()
        self.assertEqual(item.status, "pending")
        self.assertFalse(User.objects.filter(email=item.email).exists())
        self.assertFalse(AssignmentTarget.objects.filter(employee__work_email=item.email).exists())
        self.assertEqual(Employee.objects.count(), 1)
        self.assertEqual(self.client.post(PUBLIC+"status/", {"token": token}, format="json").data["status"], "pending")
        self.assertEqual(self.client.get("/api/internal/v1/objects/").status_code, 401)
        item.refresh_from_db()
        self.assertEqual(item.status, "pending")
        self.approve(item)
        user = User.objects.get(email=item.email)
        self.assertTrue(user.check_password(PASSWORD))
        self.assertEqual(user.employee.primary_location_id, self.location.pk)
        self.assertEqual(EmployeeAssignment.objects.filter(employee=user.employee, is_primary=True, status="active").count(), 1)
        item.refresh_from_db()
        self.assertEqual(item.password_hash, "")
        self.assertEqual(AssignmentTarget.objects.filter(employee=user.employee,target_type="employee").count(),1)
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.get("/api/internal/v1/assignment-targets/?search=Фамилия").data["count"],1)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_pending_approval_requires_authorized_reviewer(self):
        item, _ = self.submit()
        self.assertEqual(item.status, "pending")
        response = self.client.post(ADMIN+f"requests/{item.pk}/approve/", {"plan": self.plan}, format="json")
        self.assertEqual(response.status_code, 401)
        self.assertFalse(User.objects.filter(email=item.email).exists())


    def test_rejection_records_actor_reason_and_own_status(self):
        item, key = self.submit()
        item.refresh_from_db()
        Register.reject(registration=item, actor=self.owner, reason="Объект выбран неверно")
        item.refresh_from_db()
        self.assertEqual(item.reviewed_by_id, self.owner.pk)
        data = self.client.post(PUBLIC+"status/", {"token": key}, format="json").data
        self.assertEqual(data["status"], "rejected")
        self.assertEqual(data["rejection_reason"], "Объект выбран неверно")

    def test_repeat_does_not_overwrite_password_name_or_make_duplicate(self):
        item, _ = self.submit()
        repeated, _ = self.submit(email=" NEW@SYNTHETIC.TEST ", first_name="Подмена", password="Other-Password-123!", password_confirmation="Other-Password-123!")
        self.assertIsNone(repeated)
        self.assertEqual(RegistrationRequest.objects.count(), 1)
        item.refresh_from_db()
        self.assertEqual(item.first_name, "Имя")

    def test_public_allowlist_and_minimal_locations(self):
        data = self.client.get(PUBLIC+"locations/").data
        self.assertEqual(set(data[0]), {"id", "name"})
        payload = {**self.payload(), "location": str(self.location.pk), "role": str(self.role.pk)}
        self.assertEqual(self.client.post(PUBLIC+"submit/", payload, format="json").status_code, 400)
        ObjectService.lifecycle(user=self.owner, location=self.other, action="close", version=1, reason="test")
        self.assertNotIn(str(self.other.pk), [str(x["id"]) for x in self.client.get(PUBLIC+"locations/").data])

    def test_invite_acceptance_is_preapproval_and_old_activation_cannot_bypass(self):
        invitation, raw = Invite.issue(actor=self.owner, location=self.location, plan=self.plan, email="invite@synthetic.test")
        self.assertNotEqual(raw, invitation.token_hash)
        self.assertIsNone(InvitationService.context(raw))
        with self.assertRaises(Exception):
            InvitationService.activate(token=raw, password=PASSWORD, password_confirmation=PASSWORD)
        item, _ = self.submit(email="invite@synthetic.test", invitation=invitation)
        item.refresh_from_db(); invitation.refresh_from_db()
        self.assertEqual(item.status, "approved")
        self.assertEqual(invitation.status, "accepted")
        self.assertEqual(Employee.objects.filter(user__email=item.email).count(), 1)
        self.assertEqual(AssignmentTarget.objects.filter(employee__user__email=item.email,target_type="employee").count(),1)
        with self.assertRaises(ValidationError):
            Invite.context(raw)

    def test_email_bound_invite_and_public_immutable_location(self):
        invitation, raw = Invite.issue(actor=self.owner, location=self.location, plan=self.plan, email="bound@synthetic.test")
        with self.assertRaises(ValidationError):
            self.submit(email="wrong@synthetic.test", invitation=invitation)
        payload = {**self.payload(email="bound@synthetic.test"), "location": str(self.other.pk), "invite_token": raw}
        self.assertEqual(self.client.post(PUBLIC+"submit/", payload, format="json").status_code, 400)
        self.assertEqual(RegistrationRequest.objects.count(), 0)

    def test_expired_revoked_and_reissued_invites(self):
        old, raw = Invite.issue(actor=self.owner, location=self.location, plan=self.plan)
        EmployeeInvitation.objects.filter(pk=old.pk).update(expires_at=timezone.now()-timedelta(seconds=1), status="expired")
        with self.assertRaises(ValidationError): Invite.context(raw)
        self.client.force_authenticate(self.owner)
        response = self.client.post(ADMIN+f"invitations/{old.pk}/reissue/", {}, format="json")
        self.assertEqual(response.status_code, 201)
        with self.assertRaises(ValidationError): Invite.context(raw)
        new_raw = response.data["invitation_url"].split("#invite=")[1]
        self.assertIsNotNone(Invite.context(new_raw))
        new = EmployeeInvitation.objects.get(pk=response.data["id"])
        InvitationService.revoke(invitation=new, actor_user=self.owner)
        with self.assertRaises(ValidationError): Invite.context(new_raw)

    def test_existing_employee_requires_explicit_link_and_never_name_matching(self):
        existing = Employee.objects.create(first_name="Имя", last_name="Фамилия", work_email="new@synthetic.test")
        item, _ = self.submit()
        item.refresh_from_db()
        with self.assertRaises(ValidationError): self.approve(item)
        self.approve(item, employee=existing)
        self.assertEqual(Employee.objects.count(), 2)

    def test_returning_employee_needs_lifecycle_and_reuses_user(self):
        user = User.objects.create_user(username="returning", email="return@synthetic.test", password=PASSWORD)
        employee = Employee.objects.create(user=user, first_name="Return")
        EmployeeService.terminate(employee=employee, actor_user=self.owner); employee.refresh_from_db()
        with self.assertRaises(ValidationError): Invite.issue(actor=self.owner, location=self.location, plan=self.plan, employee=employee)
        self.assertIsNone(self.submit(email=user.email)[0])
        EmployeeService.reactivate(employee=employee, actor_user=self.owner); employee.refresh_from_db()
        invitation, _ = Invite.issue(actor=self.owner, location=self.location, plan=self.plan, email=user.email, employee=employee)
        item, _ = self.submit(email=user.email, invitation=invitation)
        user.refresh_from_db(); employee.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertEqual(employee.user_id, user.pk)
        self.assertEqual(User.objects.count(), 2)

    def test_responsibility_all_includes_new_objects_but_does_not_grant_access(self):
        employee = Employee.objects.create(first_name="Responsible")
        before = EmployeeRole.objects.count()
        ResponsibilityService.replace(employee=employee, actor=self.owner, mode="all", locations=[])
        new = self.new_object("New")
        self.assertTrue(ResponsibilityService.effective(employee).filter(pk=new.pk).exists())
        self.assertEqual(EmployeeRole.objects.count(), before)
        EmployeeService.terminate(employee=employee, actor_user=self.owner)
        employee.refresh_from_db()
        self.assertFalse(ResponsibilityService.effective(employee).exists())
        self.assertEqual(employee.object_responsibility_history.filter(valid_to__isnull=True).count(), 0)

    def test_selected_responsibility_separate_from_primary(self):
        item, _ = self.submit(); item.refresh_from_db()
        self.plan["responsibility_locations"] = [str(self.location.pk), str(self.other.pk)]
        self.approve(item)
        employee = User.objects.get(email=item.email).employee
        self.assertEqual(employee.primary_location_id, self.location.pk)
        self.assertEqual(ResponsibilityService.effective(employee).count(), 2)
        self.assertEqual(employee.access_roles.count(), 1)

    def limited_issuer(self):
        user = User.objects.create_user(username="issuer", email="issuer@synthetic.test")
        employee = Employee.objects.create(user=user, first_name="Issuer")
        authority = Role.objects.create(code="issuer", name="Issuer")
        for code in ("people.invitation.manage", "people.invitation.delegate", "people.registration.manage"):
            permission, _ = Permission.objects.get_or_create(code=code, defaults={"name": code})
            RolePermission.objects.create(role=authority, permission=permission, scope="location")
        EmployeeRole.objects.create(employee=employee, role=authority, location=self.location)
        EmployeeRole.objects.create(employee=employee, role=self.role, location=self.location)
        return user

    def test_scoped_lists_counts_details_and_delegation(self):
        issuer = self.limited_issuer()
        own, _ = self.submit()
        hidden, _ = self.submit(email="hidden@synthetic.test", location=self.other)
        self.client.force_authenticate(issuer)
        response = self.client.get(ADMIN+"requests/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(self.client.get(ADMIN+f"requests/{hidden.pk}/").status_code, 404)
        opts = self.client.get(ADMIN+"invitations/options/").data
        self.assertEqual([str(x["id"]) for x in opts["locations"]], [str(self.location.pk)])
        self.assertFalse(opts["allow_all_responsibility"])
        invite, raw = Invite.issue(actor=issuer, location=self.location, plan=self.plan)
        with self.assertRaises(PermissionDenied): Invite.issue(actor=issuer, location=self.other, plan=self.plan)
        with self.assertRaises(PermissionDenied): Invite.issue(actor=issuer, location=self.location, plan={**self.plan, "responsibility_mode": "all"})
        EmployeeRole.objects.filter(employee=issuer.employee).update(is_active=False)
        with self.assertRaises(PermissionDenied): Invite.context(raw)

    def test_archived_or_closed_object_blocks_invite_acceptance(self):
        invitation, _ = Invite.issue(actor=self.owner, location=self.location, plan=self.plan)
        ObjectService.lifecycle(user=self.owner, location=self.location, action="close", version=1, reason="test")
        with self.assertRaises(ValidationError): self.submit(invitation=invitation)
        self.assertFalse(User.objects.filter(email="new@synthetic.test").exists())


    def test_both_flows_never_create_mail_events_even_with_smtp_enabled(self):
        item, _ = self.submit()
        self.approve(item)
        invitation, _ = Invite.issue(actor=self.owner, location=self.location, plan=self.plan, email="invite-no-mail@synthetic.test")
        accepted, _ = self.submit(email="invite-no-mail@synthetic.test", invitation=invitation)
        self.assertEqual(accepted.status, "approved")
        self.assertIsNone(accepted.email_confirmed_at)
        self.assertFalse(OutboxEvent.objects.filter(event_type__in=["registration.mail.requested", "registration.invite_mail.requested"]).exists())
        provider = Mock()
        self.assertEqual(process_mail(provider=provider), 0)
        provider.send.assert_not_called()


    def test_old_mail_jobs_are_retired_without_provider_or_future_retry(self):
        item, _ = self.submit()
        event = OutboxEvent.objects.create(event_type="registration.mail.requested", entity_type="RegistrationRequest", entity_id=str(item.pk), occurred_at=timezone.now(), payload={"kind":"verify"})
        provider = Mock()
        self.assertEqual(process_mail(provider=provider), 0)
        provider.send.assert_not_called()
        event.refresh_from_db()
        self.assertEqual(event.status, "failed")
        self.assertEqual(event.last_error_code, "REGISTRATION_MAIL_DISABLED")
        self.assertIsNone(event.next_attempt_at)
        self.assertEqual(process_mail(provider=provider), 0)
        self.assertTrue(RegistrationRequest.objects.filter(pk=item.pk).exists())


    def test_retired_confirmation_resend_and_cancel(self):
        item, key = self.submit()
        self.assertEqual(self.client.post(PUBLIC+"confirm/", {"token":"old"}, format="json").status_code, 410)
        self.assertEqual(self.client.post(PUBLIC+"resend/", {"token":key}, format="json").status_code, 410)
        self.assertEqual(self.client.post(PUBLIC+"cancel/", {"token":key}, format="json").status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.password_hash, "")
        self.assertFalse(User.objects.filter(email=item.email).exists())


    def test_normalized_user_email_constraint_preserves_original_value(self):
        User.objects.create(username="odd", email=" Odd@Synthetic.Test ")
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create(username="duplicate", email="odd@synthetic.test")
        self.assertIsNone(self.submit(email="odd@synthetic.test")[0])

    def test_changed_role_permissions_invalidate_invite(self):
        invitation, raw = Invite.issue(actor=self.owner, location=self.location, plan=self.plan)
        permission, _ = Permission.objects.get_or_create(code="location.edit", defaults={"name": "Edit"})
        RolePermission.objects.create(role=self.role, permission=permission, scope="location")
        with self.assertRaises(ValidationError): Invite.context(raw)

    def test_second_email_cannot_reserve_the_same_single_use_invite(self):
        invitation, _ = Invite.issue(actor=self.owner, location=self.location, plan=self.plan)
        self.submit(invitation=invitation)

        with self.assertRaises(ValidationError): self.submit(email="second@synthetic.test", invitation=invitation)
        self.assertEqual(RegistrationRequest.objects.count(), 1)

    def test_access_scope_mutations_preserve_unrelated_assignments_and_replay(self):
        target_user = User.objects.create_user(username="scope-target", email="scope@synthetic.test")
        target = Employee.objects.create(user=target_user, first_name="Target")
        unrelated = EmployeeRole.objects.create(employee=target, role=self.role, location=self.other)
        self.client.force_authenticate(self.owner)
        endpoint = ADMIN+f"employees/{target.pk}/access/"
        payload = {"role": str(self.role.pk), "action": "assign", "access_locations": [str(self.location.pk)]}
        self.assertEqual(self.client.post(endpoint, payload, format="json").status_code, 204)
        self.assertEqual(self.client.post(endpoint, payload, format="json").status_code, 204)
        self.assertEqual(target.access_roles.filter(location=self.location, is_active=True).count(), 1)
        self.assertEqual(self.client.post(endpoint, {**payload, "action": "revoke"}, format="json").status_code, 204)
        unrelated.refresh_from_db(); self.assertTrue(unrelated.is_active)
        self.client.force_authenticate(target_user)
        self.assertEqual(self.client.post(endpoint, payload, format="json").status_code, 404)

    def test_self_signup_works_without_smtp(self):
        with override_settings(NOTIFICATIONS_EMAIL_ENABLED=False, EMAIL_HOST="", EMAIL_HOST_PASSWORD=""):
            item, key = self.submit()
            self.assertEqual(item.status, "pending")
            self.assertIsNone(item.email_confirmed_at)
            self.assertFalse(User.objects.filter(email=item.email).exists())
            self.approve(item)
            self.assertTrue(User.objects.get(email=item.email).check_password(PASSWORD))


    def test_new_viewer_cannot_read_related_people_work_requests_or_projects(self):
        from work_tasks.services import TaskService
        from projects.services import ProjectService
        from service_requests.models import ServiceCategory, Service, RequestType
        from service_requests.services import SchemaService, ServiceRequestService
        owner_employee = self.owner.employee
        task = TaskService.create(actor=owner_employee, actor_user=self.owner, title="Hidden Work", location=self.location)
        project = ProjectService.create(actor=owner_employee, actor_user=self.owner, name="Hidden Project", location=self.location, planned_end_at=timezone.now()+timedelta(days=9))
        category = ServiceCategory.objects.create(name="Synthetic")
        service = Service.objects.create(category=category, name="Synthetic")
        request_type = RequestType.objects.create(service=service, name="Synthetic", code="REGISTRATION", created_by=owner_employee)
        SchemaService.publish(request_type, owner_employee, self.owner)
        work_request = ServiceRequestService.create(actor=owner_employee, actor_user=self.owner, request_type=request_type, subject="Hidden Request", payload={}, location=self.location)
        item, _ = self.submit(); item.refresh_from_db(); self.approve(item)
        user = User.objects.get(email=item.email)
        self.client.force_authenticate(user)
        for kind in ("tasks", "requests", "projects", "participating_projects"):
            result = self.client.get(f"/api/internal/v1/objects/{self.location.pk}/related/?kind={kind}")
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.data["count"], 0)
        for path in [f"tasks/{task.pk}/", f"requests/{work_request.pk}/", f"projects/{project.pk}/", f"people/employees/{owner_employee.pk}/"]:
            self.assertEqual(self.client.get("/api/internal/v1/"+path).status_code, 404, path)
        for domain in ("tasks", "requests", "projects"):
            result = self.client.get(f"/api/internal/v1/{domain}/")
            self.assertIn(result.status_code, [200, 403])
            if result.status_code == 200: self.assertEqual(result.data["count"], 0)

    def test_legacy_creation_paths_cannot_issue_unbound_invites(self):
        self.client.force_authenticate(self.owner)
        before = EmployeeInvitation.objects.count()
        self.assertEqual(self.client.post("/api/internal/v1/people/invitations/", {"employee": str(self.owner.employee.pk)}, format="json").status_code, 400)
        self.assertEqual(EmployeeInvitation.objects.count(), before)

    def test_legacy_role_assignment_requires_explicit_rbac_authority(self):
        issuer = self.limited_issuer()
        permission, _ = Permission.objects.get_or_create(code="employee.manage", defaults={"name": "Manage employees"})
        RolePermission.objects.create(role=Role.objects.get(code="issuer"), permission=permission, scope="global")
        self.client.force_authenticate(issuer)
        before = EmployeeRole.objects.count()
        response = self.client.post(f"/api/internal/v1/employees/{self.owner.employee.pk}/roles/", {"role": str(self.role.pk)}, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(EmployeeRole.objects.count(), before)

    def test_unsafe_own_administrative_grant_is_not_delegated(self):
        permission, _ = Permission.objects.get_or_create(code="role.manage", defaults={"name": "RBAC"})
        RolePermission.objects.create(role=self.role, permission=permission, scope="own")
        with self.assertRaises(ValidationError): Invite.issue(actor=self.owner, location=self.location, plan=self.plan)

    def test_fill_employment_preserves_existing_account_and_legal_context(self):
        from organizations.models import LegalEntity
        legal = LegalEntity.objects.create(name="Existing legal entity")
        user = User.objects.create_user(username="existing-employment", email="existing@synthetic.test", password=PASSWORD)
        employee = Employee.objects.create(user=user, first_name="Existing", legal_entity=legal)
        baseline = User.objects.values().get(pk=user.pk)
        self.client.force_authenticate(self.owner)
        url = ADMIN+f"employees/{employee.pk}/employment/"
        self.assertEqual(self.client.post(url,{"location":str(self.location.pk)},format="json").status_code,200)
        self.assertEqual(self.client.post(url,{"location":str(self.other.pk)},format="json").status_code,200)
        employee.refresh_from_db()
        self.assertEqual(employee.primary_location_id,self.other.pk)
        self.assertEqual(employee.legal_entity_id,legal.pk)
        self.assertEqual(employee.organizational_assignments.filter(status="active",is_primary=True).count(),1)
        self.assertEqual(employee.organizational_assignments.count(),2)
        self.assertEqual(User.objects.values().get(pk=user.pk),baseline)

    def test_public_rate_limit_uses_shared_database_counter(self):
        from rest_framework.settings import api_settings
        rates = {**api_settings.DEFAULT_THROTTLE_RATES, "registration_locations": "1/hour"}
        from django.conf import settings
        with override_settings(REST_FRAMEWORK={**settings.REST_FRAMEWORK,"DEFAULT_THROTTLE_RATES":rates}):
            self.assertEqual(APIClient().get(PUBLIC+"locations/").status_code,200)
            self.assertEqual(APIClient().get(PUBLIC+"locations/").status_code,429)

    def test_state_consumer_acknowledges_projection_without_claiming_mail_delivery(self):
        from .registration_events import process_state_events
        item, _ = self.submit()
        self.assertEqual(process_state_events(),1)
        state = OutboxEvent.objects.get(event_type="registration.submitted")
        self.assertEqual(state.payload["consumer_receipt"],"transactional_state_projection")
        self.assertFalse(OutboxEvent.objects.filter(event_type="registration.mail.requested").exists())
        self.assertEqual(process_state_events(),0)

    def test_deactivation_of_superuser_inviter_blocks_acceptance(self):
        invitation, raw = Invite.issue(actor=self.owner,location=self.location,plan=self.plan)
        EmployeeService.deactivate(employee=self.owner.employee,actor_user=self.owner)
        with self.assertRaises(PermissionDenied): Invite.context(raw)
        with self.assertRaises(PermissionDenied): self.submit(invitation=invitation)
        self.assertFalse(User.objects.filter(email="new@synthetic.test").exists())


    def test_invite_default_is_minimal_view_role_and_single_employment_scope(self):
        invitation, _ = Invite.issue(actor=self.owner,location=self.location)
        role = Role.objects.get(pk=invitation.access_plan["role"])
        self.assertEqual(role.code,"employee_objects_viewer")
        self.assertEqual(invitation.access_plan["access_locations"],[str(self.location.pk)])
        self.assertEqual(invitation.access_plan["responsibility_mode"],"selected")
        self.assertEqual(invitation.access_plan["responsibility_locations"],[])

    def test_modified_default_role_cannot_silently_add_write_privileges(self):
        role = Role.objects.get(code="employee_objects_viewer")
        permission, _ = Permission.objects.get_or_create(code="location.edit",defaults={"name":"Edit"})
        RolePermission.objects.create(role=role,permission=permission,scope="location")
        with self.assertRaises(ValidationError): Invite.issue(actor=self.owner,location=self.location)

    def test_readonly_signup_has_no_implicit_legacy_api_privileges(self):
        from accounts.serializers import EmailTokenSerializer
        item, _ = self.submit(); item.refresh_from_db(); self.approve(item)
        user = User.objects.get(email=item.email)
        access = str(EmailTokenSerializer.get_token(user).access_token)
        client = APIClient(); client.credentials(HTTP_AUTHORIZATION="Bearer "+access)
        for namespace in ("tasks", "sensors", "incidents", "checklists"):
            self.assertEqual(client.get(f"/api/v1/{namespace}/").status_code,403)
        self.assertEqual(client.post("/api/v1/tasks/", {"title":"Forbidden legacy write"}, format="json").status_code,403)
        self.assertEqual(client.get(f"/api/internal/v1/objects/{self.location.pk}/").status_code,200)
        self.assertEqual(client.get("/api/v1/employees/dashboard/").status_code,200)
        from accounts.registration_boundary import legacy_access_allowed
        previous = User.objects.create_user(username="previous-user",email="previous@synthetic.test")
        self.assertTrue(legacy_access_allowed(previous))

    def test_invalid_request_filter_is_validation_error(self):
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.get(ADMIN+"requests/?employment_location=not-a-uuid").status_code,400)
        self.assertEqual(self.client.get(ADMIN+"requests/?status=unknown").status_code,400)


    def test_upgrade_retires_old_confirmation_without_activating_or_sending(self):
        from importlib import import_module
        from django.apps import apps
        item, _ = self.submit()
        RegistrationRequest.objects.filter(pk=item.pk).update(status="email_pending")
        legacy = RegistrationRequest.objects.create(email="old@synthetic.test", full_name="Legacy", status="pending", expires_at=timezone.now()+timedelta(days=1))
        mail = OutboxEvent.objects.create(event_type="registration.mail.requested", entity_type="RegistrationRequest", entity_id=str(item.pk), occurred_at=timezone.now(), next_attempt_at=timezone.now())
        import_module("employees.migrations.0020_retire_registration_verification").retire(apps, None)
        item.refresh_from_db(); legacy.refresh_from_db(); mail.refresh_from_db()
        self.assertEqual(item.status, "cancelled")
        self.assertEqual(item.password_hash, "")
        self.assertEqual(legacy.status, "pending")
        self.assertFalse(User.objects.filter(email=item.email).exists())
        self.assertEqual(mail.last_error_code, "REGISTRATION_MAIL_DISABLED")
        self.assertIsNone(mail.next_attempt_at)
        self.assertTrue(AuditEvent.objects.filter(action="registration.verification_retired", entity_id=str(item.pk)).exists())
        self.assertTrue(OutboxEvent.objects.filter(event_type="registration.cancelled", entity_id=str(item.pk)).exists())


class ConcurrentRegistrationTests(Setup, TransactionTestCase):
    def parallel(self, fn):
        def run(_):
            close_old_connections()
            try: return fn()
            finally: connection.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(run, range(2)))

    def test_parallel_submissions_create_one_request(self):
        self.parallel(lambda: self.submit())
        self.assertEqual(RegistrationRequest.objects.count(), 1)

    def test_parallel_invite_submit_creates_one_user_employee_and_assignment(self):
        invitation, _ = Invite.issue(actor=self.owner, location=self.location, plan=self.plan)
        self.parallel(lambda: self.submit(invitation=EmployeeInvitation.objects.get(pk=invitation.pk)))
        self.assertEqual(User.objects.filter(email="new@synthetic.test").count(), 1)
        employee = Employee.objects.get(user__email="new@synthetic.test")
        self.assertEqual(EmployeeAssignment.objects.filter(employee=employee, status="active", is_primary=True).count(), 1)
        self.assertEqual(EmployeeRole.objects.filter(employee=employee, is_active=True).count(), 1)
        self.assertEqual(AssignmentTarget.objects.filter(employee=employee,target_type="employee").count(),1)


    def test_invite_submit_works_without_smtp(self):
        with override_settings(NOTIFICATIONS_EMAIL_ENABLED=False, EMAIL_HOST=""):
            invitation, _ = Invite.issue(actor=self.owner, location=self.location, plan=self.plan)
            item, _ = self.submit(invitation=invitation)
            self.assertEqual(item.status, "approved")
            self.assertFalse(OutboxEvent.objects.filter(event_type__contains="mail.requested").exists())


    def test_parallel_public_throttles_cannot_bypass_single_slot(self):
        from .registration_throttle import RegistrationThrottle
        from rest_framework.settings import api_settings
        from django.conf import settings
        rates = {**api_settings.DEFAULT_THROTTLE_RATES, "registration_locations": "1/hour"}
        class View: throttle_scope = "registration_locations"
        class Request: META = {"REMOTE_ADDR": "192.0.2.1"}
        with override_settings(REST_FRAMEWORK={**settings.REST_FRAMEWORK,"DEFAULT_THROTTLE_RATES":rates}):
            results = self.parallel(lambda: RegistrationThrottle().allow_request(Request(),View()))
        self.assertEqual(results.count(True),1)

    def test_parallel_emails_cannot_claim_one_invite_twice(self):
        invitation, _ = Invite.issue(actor=self.owner, location=self.location, plan=self.plan)
        def run(email):
            close_old_connections()
            try:
                try: return self.submit(email=email,invitation=EmployeeInvitation.objects.get(pk=invitation.pk))[0]
                except ValidationError: return None
            finally: connection.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(run,["one@synthetic.test","two@synthetic.test"]))
        self.assertEqual(RegistrationRequest.objects.count(),1)
