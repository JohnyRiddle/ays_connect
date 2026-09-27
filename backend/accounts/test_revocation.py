import secrets
from importlib import import_module
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user, get_user_model
from django.test import Client, RequestFactory, TestCase, override_settings
from rest_framework.test import APIClient

from employees.models import Employee
from employees.onboarding import InvitationService
from employees.services import AccountAccessService, EmployeeService
from .serializers import EmailTokenSerializer


@override_settings(CACHES={"default": {
    "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    "LOCATION": "credential-revocation-tests",
}})
class CredentialRevocationTests(TestCase):
    def setUp(self):
        self.password = secrets.token_urlsafe(32)
        self.user = get_user_model().objects.create_user(
            username="revoke-synthetic", email="revoke@example.test", password=self.password,
        )
        self.actor = get_user_model().objects.create_user(username="revoke-actor", email="actor@example.test")
        self.employee = Employee.objects.create(user=self.user, first_name="Synthetic",
                                               employee_number="REVOKE-1", work_email=self.user.email)
        self.client = APIClient()

    def pair(self):
        self.user.refresh_from_db()
        refresh = EmailTokenSerializer.get_token(self.user)
        return str(refresh.access_token), str(refresh)

    def assert_denied(self, pair):
        access, refresh = pair
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(self.client.get('/api/v1/auth/me/').status_code, 401)
        self.client.credentials()
        self.assertEqual(self.client.post('/api/v1/auth/refresh/', {"refresh": refresh}).status_code, 401)

    def suspend(self):
        AccountAccessService.set_access(employee=self.employee, actor_user=self.actor,
                                       enabled=False, action="suspended")

    def restore(self):
        AccountAccessService.set_access(employee=self.employee, actor_user=self.actor,
                                       enabled=True, action="restored")

    def test_old_access_and_refresh_denied_after_restore_new_login_works(self):
        old = self.pair()
        self.suspend()
        self.assert_denied(old)
        self.restore()
        self.assert_denied(old)
        response = self.client.post('/api/v1/auth/login/', {"email": self.user.email, "password": self.password})
        self.assertEqual(response.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        self.assertEqual(self.client.get('/api/v1/auth/me/').status_code, 200)
        self.client.credentials()
        response = self.client.post('/api/v1/auth/refresh/', {"refresh": response.data['refresh']})
        self.assertEqual(response.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        self.assertEqual(self.client.get('/api/v1/auth/me/').status_code, 200)

    def test_unvisited_django_session_does_not_revive_after_restore(self):
        browser = Client()
        browser.force_login(self.user)
        session_key = browser.session.session_key
        self.suspend()
        self.restore()
        request = RequestFactory().get('/')
        request.session = import_module(settings.SESSION_ENGINE).SessionStore(session_key=session_key)
        self.assertFalse(get_user(request).is_authenticated)

    def test_termination_rehire_and_activation_keep_old_credentials_revoked(self):
        old = self.pair()
        employee_id, user_id, number = self.employee.pk, self.user.pk, self.employee.employee_number
        EmployeeService.terminate(employee=self.employee, actor_user=self.actor)
        self.assert_denied(old)
        EmployeeService.reactivate(employee=self.employee, actor_user=self.actor)
        _, raw = InvitationService.issue(employee=self.employee, actor_user=self.actor,
                                         delivery_address=self.user.email)
        password = secrets.token_urlsafe(32)
        restored = InvitationService.activate(token=raw, password=password, password_confirmation=password)
        self.employee.refresh_from_db()
        self.assertEqual((self.employee.pk, restored.pk, self.employee.employee_number), (employee_id, user_id, number))
        self.assert_denied(old)
        access, _ = self.pair()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(self.client.get('/api/v1/auth/me/').status_code, 200)

    def test_audit_failure_does_not_revoke_credentials(self):
        old = self.pair()
        with patch('employees.services.AuditService.record', side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.suspend()
        self.user.refresh_from_db()
        self.assertEqual(self.user.auth_version, 0)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {old[0]}")
        self.assertEqual(self.client.get('/api/v1/auth/me/').status_code, 200)

    def test_other_users_credentials_remain_valid(self):
        other = EmailTokenSerializer.get_token(self.actor)
        self.suspend()
        self.restore()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {other.access_token}")
        self.assertEqual(self.client.get('/api/v1/auth/me/').status_code, 200)

    def test_legacy_claimless_token_is_valid_only_before_first_revoke(self):
        from rest_framework_simplejwt.tokens import RefreshToken
        legacy = RefreshToken.for_user(self.user)
        pair = str(legacy.access_token), str(legacy)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {pair[0]}")
        self.assertEqual(self.client.get('/api/v1/auth/me/').status_code, 200)
        self.client.credentials()
        self.suspend()
        self.restore()
        self.assert_denied(pair)

    def test_restore_of_pre_migration_suspended_account_revokes_legacy_token(self):
        from rest_framework_simplejwt.tokens import RefreshToken
        legacy = RefreshToken.for_user(self.user)
        old = str(legacy.access_token), str(legacy)
        get_user_model().objects.filter(pk=self.user.pk).update(is_active=False)
        self.restore()
        self.assert_denied(old)

    def test_repeated_termination_keeps_revocation_idempotent(self):
        EmployeeService.terminate(employee=self.employee, actor_user=self.actor)
        self.user.refresh_from_db()
        version = self.user.auth_version
        EmployeeService.terminate(employee=self.employee, actor_user=self.actor)
        self.user.refresh_from_db()
        self.assertEqual(self.user.auth_version, version)

    def test_stale_user_save_cannot_undo_revocation(self):
        stale = get_user_model().objects.get(pk=self.user.pk)
        self.suspend()
        stale.first_name = "Synthetic changed"
        stale.save()
        self.user.refresh_from_db()
        self.assertEqual(self.user.auth_version, 1)

    def test_admin_forms_cannot_write_lifecycle_fields(self):
        from django.contrib import admin
        request = RequestFactory().get('/admin/')
        request.user = get_user_model()(is_active=True, is_staff=True, is_superuser=True)
        for model, obj, forbidden in [
            (get_user_model(), self.user, {'is_active','auth_version'}),
            (Employee, self.employee, {'user','is_active','status','account_access_state','dismissed_at'}),
        ]:
            model_admin = admin.site._registry[model]
            form = model_admin.get_form(request, obj)
            self.assertFalse(forbidden.intersection(form.base_fields))
            self.assertFalse(model_admin.has_delete_permission(request,obj))

    def test_generic_employee_patch_cannot_toggle_access_or_replace_user(self):
        from employees.internal_api import EmployeeInternalSerializer,EmployeeViewSet
        from rest_framework.exceptions import ValidationError
        for changes in [{'is_active':False},{'status':'terminated'},{'user':self.actor.pk},{'account_access_state':'normal'}]:
            serializer=EmployeeInternalSerializer(self.employee,data={**changes,'first_name':'Must not persist'},partial=True)
            self.assertFalse(serializer.is_valid())
        self.employee.refresh_from_db()
        self.assertTrue(self.employee.is_active)
        self.assertEqual(self.employee.user_id,self.user.pk)
        self.assertEqual(self.employee.first_name,'Synthetic')
        with self.assertRaises(ValidationError):EmployeeViewSet().perform_destroy(self.employee)
        self.assertTrue(Employee.objects.filter(pk=self.employee.pk).exists())

    def test_legacy_people_block_unblock_endpoints_do_not_revive_tokens(self):
        from access_control.models import Role, Permission, RolePermission, EmployeeRole
        actor = Employee.objects.create(user=self.actor, employee_number='REVOKE-ACTOR')
        role = Role.objects.create(code='revoke-maintainer', name='Synthetic maintainer')
        for code in ['people.employee.view','people.account.manage']:
            permission,_=Permission.objects.get_or_create(code=code)
            RolePermission.objects.create(role=role,permission=permission,scope='global')
        EmployeeRole.objects.create(employee=actor,role=role)
        old=self.pair()
        operator=APIClient();operator.force_authenticate(self.actor)
        path=f'/api/internal/v1/people/employees/{self.employee.pk}/account/'
        self.assertEqual(operator.post(path+'block/',{}).status_code,200)
        self.assert_denied(old)
        self.assertEqual(operator.post(path+'unblock/',{}).status_code,200)
        self.assert_denied(old)
