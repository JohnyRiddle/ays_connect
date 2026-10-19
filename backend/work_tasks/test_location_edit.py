from django.test import TestCase
from rest_framework.test import APIClient
from access_control.models import EmployeeRole, Role, Permission, RolePermission
from organizations.models import LegalEntity
from organizations.object_services import ObjectService
from audit.models import AuditEvent
from . import test_task_patch as patch_fixture
from uuid import uuid4

def grant(employee, codes, scope='global'):
    role=Role.objects.create(code=f'location-test-{uuid4()}',name='Synthetic location role')
    for code in codes:
        permission,_=Permission.objects.get_or_create(code=code,defaults={'name':code})
        RolePermission.objects.create(role=role,permission=permission,scope=scope)
    EmployeeRole.objects.create(employee=employee,role=role)
    return role


class TaskLocationEditTests(TestCase):
    def setUp(self):
        patch_fixture.TaskPatchTests.setUp(self)
        entity = LegalEntity.objects.create(name='Synthetic location edit')
        self.locations = [ObjectService.create(user=self.admin, key=f'edit-location-{i}', data={
            'name': f'Synthetic location {i}', 'business_type': 'office',
            'timezone': 'UTC', 'legal_entity': entity})[0] for i in range(2)]
        self.source, self.target_location = self.locations
        self.head_role = grant(self.head, ['location.view'], 'global')
        self.task = patch_fixture.TaskPatchTests.create(self, location=self.source)
        self.client = APIClient(); self.client.force_authenticate(self.admin)
        self.url = f'/api/internal/v1/tasks/{self.task.pk}/'

    def patch(self, location, **extra):
        return self.client.patch(self.url, {'version': self.task.version, 'location': str(location.pk) if location else None, **extra}, format='json')

    def assert_unchanged(self, response):
        self.assertGreaterEqual(response.status_code, 400)
        self.task.refresh_from_db()
        self.assertEqual(self.task.location, self.source)
        self.assertEqual(self.task.version, 1)
        self.assertFalse(AuditEvent.objects.filter(entity_id=str(self.task.pk), action='task.updated').exists())

    def test_change_and_clear_preserve_task_and_audit(self):
        before = (self.task.status, self.task.responsible_employee_id, self.task.due_at)
        self.assertEqual(self.patch(self.target_location).status_code, 200)
        self.task.refresh_from_db(); self.assertEqual(self.task.location, self.target_location)
        self.assertEqual((self.task.status, self.task.responsible_employee_id, self.task.due_at), before)
        self.assertEqual(self.patch(None).status_code, 200)
        self.task.refresh_from_db(); self.assertIsNone(self.task.location)
        self.assertEqual(AuditEvent.objects.filter(entity_id=str(self.task.pk), action='task.updated').count(), 2)

    def scope_actor(self, location):
        grant(self.member, ['task.view','task.edit'], 'global')
        role = grant(self.member, ['location.view'], 'location')
        EmployeeRole.objects.filter(employee=self.member, role=role).update(location=location)
        self.client.force_authenticate(self.member_user)

    def test_actor_needs_source_location_access(self):
        self.scope_actor(self.target_location)
        self.assert_unchanged(self.patch(self.target_location))

    def test_actor_needs_target_location_access(self):
        self.scope_actor(self.source)
        self.assert_unchanged(self.patch(self.target_location))

    def test_task_edit_permission_is_required(self):
        self.client.force_authenticate(self.other_user)
        self.assert_unchanged(self.patch(self.target_location))

    def test_responsible_without_target_access_is_rejected(self):
        EmployeeRole.objects.filter(employee=self.head, role=self.head_role).update(is_active=False)
        self.assert_unchanged(self.patch(self.target_location))

    def test_executor_without_target_access_is_rejected(self):
        self.task.executor_employee=self.member; self.task.save(update_fields=['executor_employee'])
        self.assert_unchanged(self.patch(self.target_location))

    def test_stale_version_is_rejected(self):
        self.assert_unchanged(self.patch(self.target_location, version=99))
