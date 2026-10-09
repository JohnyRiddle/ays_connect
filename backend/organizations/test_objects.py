from concurrent.futures import ThreadPoolExecutor
import threading
from unittest.mock import patch
import uuid

from django.contrib import admin
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient
from rest_framework.exceptions import ValidationError, PermissionDenied

from accounts.models import User
from access_control.models import Permission, Role, RolePermission, EmployeeRole
from audit.models import AuditEvent
from events.models import OutboxEvent
from employees.models import Employee, EmployeeAssignment
from employees.services import EmployeeService
from .models import Location, LocationResponsibility, LocationIdempotency, LegalEntity
from .object_services import ObjectService, ObjectConflict, object_write
from .object_policies import LocationAccessPolicy


class ObjectsSetup:
    def setup_objects(self):
        self.user = User.objects.create_superuser(username="objects-synthetic", email="objects@synthetic.test", password="synthetic")
        self.actor = Employee.objects.create(user=self.user, first_name="Синтетический", is_demo=True)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def create_object(self, **data):
        item, _ = ObjectService.create(user=self.user, key=str(uuid.uuid4()), data={"name": "Синтетический объект", "business_type": "office", "timezone": "Asia/Novosibirsk", **data})
        return item

    def limited(self, scope, context=None, codes=("location.view",)):
        identifier = str(uuid.uuid4())
        user = User.objects.create_user(username=f"limited-{identifier}", email=f"{identifier}@synthetic.test")
        actor = Employee.objects.create(user=user, first_name="Синтетический", is_demo=True)
        role = Role.objects.create(code=str(uuid.uuid4()), name="Синтетическая роль")
        for code in codes:
            permission, _ = Permission.objects.get_or_create(code=code, defaults={"name": code})
            RolePermission.objects.create(role=role, permission=permission, scope=scope)
        assignment = EmployeeRole.objects.create(employee=actor, role=role, **(context or {}))
        return user, assignment


class ObjectsTests(ObjectsSetup, TestCase):
    def setUp(self):
        self.setup_objects()

    def test_create_requires_visibility_and_manage_does_not_imply_view(self):
        for codes in (("location.create",), ("location.manage",)):
            user, _ = self.limited("global", codes=codes)
            with self.assertRaises(PermissionDenied):
                ObjectService.create(user=user, key="no-view", data={"name":"Invisible result", "business_type":"office", "timezone":"Asia/Novosibirsk"})
            self.client.force_authenticate(user)
            self.assertFalse(self.client.get("/api/internal/v1/objects/capabilities/").data["can_create"])
        self.assertFalse(Location.objects.exists())
        self.assertFalse(LocationIdempotency.objects.exists())

    def test_inactive_user_grants_fail_closed(self):
        item = self.create_object()
        user, _ = self.limited("global", codes=("location.view", "location.edit"))
        user.is_active = False
        user.save()
        self.assertFalse(LocationAccessPolicy.visible(user).exists())
        with self.assertRaises(PermissionDenied):
            ObjectService.edit(location=item, user=user, version=1, data={"name":"Denied"})

    def test_legacy_api_and_admin_mask_hidden_relations(self):
        from django.test import RequestFactory
        with object_write():
            parent = Location.objects.create(name="Hidden geography",node_kind="geography",timezone="Asia/Novosibirsk")
        legal = LegalEntity.objects.create(name="Hidden legal")
        item = self.create_object(parent=parent, legal_entity=legal)
        user, _ = self.limited("location", {"location":item})
        self.client.force_authenticate(user)
        response = self.client.get(f"/api/internal/v1/locations/{item.pk}/")
        self.assertEqual(response.status_code,200)
        self.assertIsNone(response.data["parent"])
        self.assertIsNone(response.data["legal_entity"])
        request = RequestFactory().get("/admin/")
        request.user = user
        fields = admin.site._registry[Location].get_fields(request,item)
        self.assertNotIn("parent",fields)
        self.assertNotIn("legal_entity",fields)

    def test_restore_zone_under_archived_object_is_validation_error(self):
        item = self.create_object()
        zone = ObjectService.zone(parent=item,user=self.user,version=1,name="Zone")
        zone = ObjectService.lifecycle(location=zone,user=self.user,version=1,action="archive")
        item.refresh_from_db()
        item = ObjectService.lifecycle(location=item,user=self.user,version=item.version,action="close",reason="Synthetic")
        item = ObjectService.lifecycle(location=item,user=self.user,version=item.version,action="archive")
        response = self.client.post(f"/api/internal/v1/objects/{zone.pk}/lifecycle/",{"version":zone.version,"action":"restore"},format="json")
        self.assertEqual(response.status_code,400,response.data)
        zone.refresh_from_db()
        self.assertTrue(zone.is_archived)

    def test_minimal_create_retry_and_key_conflict(self):
        payload = {"name": "Объект", "business_type": "bar", "timezone": "Asia/Novosibirsk"}
        response = self.client.post("/api/internal/v1/objects/", payload, format="json", HTTP_IDEMPOTENCY_KEY="first")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["business_status"], "preparation")
        self.assertTrue(response.data["code"].startswith("OBJ-"))
        repeated = self.client.post("/api/internal/v1/objects/", payload, format="json", HTTP_IDEMPOTENCY_KEY="first")
        self.assertEqual(repeated.status_code, 200, repeated.data)
        self.assertEqual(repeated.data["id"], response.data["id"])
        conflict = self.client.post("/api/internal/v1/objects/", {**payload, "name": "Другой"}, format="json", HTTP_IDEMPOTENCY_KEY="first")
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(LocationIdempotency.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.filter(action="location.created").count(), 1)
        self.assertEqual(OutboxEvent.objects.filter(event_type="location.created").count(), 1)

    def test_input_allowlist_timezone_and_required_key(self):
        payload = {"name": "Объект", "business_type": "bar", "timezone": "Asia/Novosibirsk"}
        for changed in [{"code": "OBJ-1"}, {"version": 10}, {"id": str(uuid.uuid4())}, {"is_archived": True}, {"timezone": "Bogus/Invalid"}]:
            result = self.client.post("/api/internal/v1/objects/", {**payload, **changed}, format="json", HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
            self.assertEqual(result.status_code, 400, result.data)
        self.assertEqual(self.client.post("/api/internal/v1/objects/", payload, format="json").status_code, 400)
        self.assertEqual(Location.objects.count(), 0)

    def test_full_card_and_termination_history(self):
        legal = LegalEntity.objects.create(name="Синтетическое юрлицо")
        employee = Employee.objects.create(first_name="Ответственный", is_demo=True)
        item = self.create_object(legal_entity=legal, address="Синтетический адрес", manager=employee, technical=employee, contacts="demo", work_schedule="24/7", description="synthetic")
        self.assertEqual(LocationResponsibility.objects.filter(location=item, valid_to__isnull=True).count(), 2)
        EmployeeService.terminate(employee=employee, actor_user=self.user)
        self.assertFalse(LocationResponsibility.objects.filter(location=item, valid_to__isnull=True).exists())
        self.assertEqual(LocationResponsibility.objects.filter(location=item, end_reason="employee_terminated").count(), 2)
        EmployeeService.reactivate(employee=employee, actor_user=self.user)
        self.assertFalse(LocationResponsibility.objects.filter(location=item, valid_to__isnull=True).exists())

    def test_audit_and_outbox_failure_roll_back_all_parts(self):
        employee = Employee.objects.create(first_name="Ответственный", is_demo=True)
        for target in ["organizations.object_services.AuditService.record", "organizations.object_services.DomainEventService.publish"]:
            with patch(target, side_effect=RuntimeError("synthetic")):
                with self.assertRaises(RuntimeError):
                    self.create_object(manager=employee)
            self.assertEqual(Location.objects.count(), 0)
            self.assertEqual(LocationResponsibility.objects.count(), 0)
            self.assertEqual(LocationIdempotency.objects.count(), 0)
            self.assertEqual(AuditEvent.objects.filter(action="location.created").count(), 0)

    def test_duplicate_confirmation_visible_only(self):
        self.create_object(name="  СИНТЕТИЧЕСКИЙ объект ")
        with self.assertRaises(ValidationError):
            self.create_object()
        second = self.create_object(confirm_duplicate=True)
        self.assertEqual(Location.objects.filter(node_kind="object").count(), 2)
        legal = LegalEntity.objects.create(name="Scoped")
        user, _ = self.limited("legal_entity", {"legal_entity": legal}, ("location.create", "location.view", "organization.view"))
        item, _ = ObjectService.create(user=user, key="hidden-duplicate", data={"name": second.name, "business_type": "office", "timezone": "Asia/Novosibirsk", "legal_entity": legal})
        self.assertEqual(item.legal_entity, legal)

    def test_scoped_create_null_and_unavailable_relations(self):
        legal = LegalEntity.objects.create(name="Scoped")
        user, _ = self.limited("legal_entity", {"legal_entity": legal}, ("location.create", "location.view", "organization.view"))
        item, _ = ObjectService.create(user=user, key="scoped", data={"name": "Scoped", "business_type": "office", "timezone": "Asia/Novosibirsk", "legal_entity": legal})
        self.assertEqual(item.legal_entity, legal)
        with self.assertRaises(PermissionDenied):
            ObjectService.create(user=user, key="root", data={"name": "Root", "business_type": "office", "timezone": "Asia/Novosibirsk"})
        null_user, _ = self.limited("legal_entity", {}, ("location.create",))
        self.client.force_authenticate(null_user)
        response = self.client.post("/api/internal/v1/objects/", {"name": "Root", "business_type": "office", "timezone": "Asia/Novosibirsk"}, format="json", HTTP_IDEMPOTENCY_KEY="null")
        self.assertEqual(response.status_code, 403, response.data)

    def test_scope_lists_lookups_and_idor(self):
        first = self.create_object(name="First")
        second = self.create_object(name="Second")
        zone = ObjectService.zone(parent=first, user=self.user, version=first.version, name="Зона")
        user, _ = self.limited("location", {"location": first})
        self.client.force_authenticate(user)
        self.assertEqual(self.client.get("/api/internal/v1/objects/").data["count"], 1)
        self.assertEqual(self.client.get("/api/internal/v1/locations/").data["count"], 2)
        self.assertEqual(self.client.get(f"/api/internal/v1/objects/{second.pk}/").status_code, 404)
        self.assertEqual(self.client.get(f"/api/internal/v1/objects/{first.pk}/zones/").data["count"], 1)
        self.assertEqual(self.client.get("/api/internal/v1/objects/lookups/").data["parents"], [])
        self.assertEqual(self.client.patch(f"/api/internal/v1/objects/{zone.pk}/", {"version": 1, "name": "Forbidden"}, format="json").status_code, 403)

    def test_revoked_access_before_retry(self):
        user, grant = self.limited("global", {}, ("location.create", "location.view"))
        payload = {"name": "New", "business_type": "office", "timezone": "Asia/Novosibirsk"}
        self.client.force_authenticate(user)
        self.assertEqual(self.client.post("/api/internal/v1/objects/", payload, format="json", HTTP_IDEMPOTENCY_KEY="retry").status_code, 201)
        grant.is_active = False
        grant.save()
        self.assertEqual(self.client.post("/api/internal/v1/objects/", payload, format="json", HTTP_IDEMPOTENCY_KEY="retry").status_code, 403)

    def test_zones_invalid_parent_stale_version_and_cycle(self):
        item = self.create_object()
        zone = ObjectService.zone(parent=item, user=self.user, version=1, name="Zone")
        child = ObjectService.zone(parent=zone, user=self.user, version=1, name="Child")
        for depth in range(32):
            child = ObjectService.zone(parent=child, user=self.user, version=child.version, name=f"Deep zone {depth}")
        with self.assertRaises(ObjectConflict):
            ObjectService.edit(location=item, user=self.user, version=1, data={"name": "Old"})
        zone.refresh_from_db()
        with self.assertRaises(ValidationError):
            ObjectService.move(location=zone, parent=child, user=self.user, version=zone.version)
        with self.assertRaises(ValidationError):
            self.create_object(name="Nested object", parent=item)

    def test_lifecycle_archive_privacy_and_restore(self):
        item = self.create_object()
        with self.assertRaises(ValidationError):
            ObjectService.lifecycle(location=item, user=self.user, version=1, action="operate")
        closed = ObjectService.lifecycle(location=item, user=self.user, version=1, action="close", reason="Synthetic")
        EmployeeAssignment.objects.create(employee=self.actor, location=closed)
        result = self.client.post(f"/api/internal/v1/objects/{closed.pk}/lifecycle/", {"version": closed.version, "action": "archive"}, format="json")
        self.assertEqual(result.status_code, 400)
        self.assertNotIn(self.actor.first_name, str(result.data))
        EmployeeAssignment.objects.filter(location=closed).update(status="ended")
        archived = ObjectService.lifecycle(location=closed, user=self.user, version=closed.version, action="archive")
        restored = ObjectService.lifecycle(location=archived, user=self.user, version=archived.version, action="restore")
        self.assertEqual(restored.business_status, "final_closed")
        reopened = ObjectService.lifecycle(location=restored, user=self.user, version=restored.version, action="reopen", reason="Synthetic")
        self.assertEqual(reopened.business_status, "preparation")

    def test_seasonal_status_has_no_people_side_effect(self):
        employee = Employee.objects.create(first_name="Manager", is_demo=True)
        legal = LegalEntity.objects.create(name="LE")
        item = self.create_object(manager=employee, legal_entity=legal, address="Synthetic address")
        item = ObjectService.lifecycle(location=item, user=self.user, version=item.version, action="operate")
        item = ObjectService.lifecycle(location=item, user=self.user, version=item.version, action="seasonal_close", reason="Winter")
        employee.refresh_from_db()
        self.assertTrue(employee.is_active)
        self.assertEqual(LocationResponsibility.objects.filter(location=item, valid_to__isnull=True).count(), 1)
        item = ObjectService.lifecycle(location=item, user=self.user, version=item.version, action="operate", reason="Summer")
        self.assertEqual(item.business_status, "operating")

    def test_old_api_admin_and_direct_orm_bypass_blocked(self):
        item = self.create_object()
        self.assertEqual(self.client.post("/api/internal/v1/locations/", {"name": "Bypass"}, format="json").status_code, 405)
        self.assertEqual(self.client.delete(f"/api/internal/v1/objects/{item.pk}/").status_code, 405)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Location.objects.filter(pk=item.pk).update(name="Bypass")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Location.objects.filter(pk=item.pk).delete()
        self.assertFalse(admin.site._registry[Location].has_change_permission(None, item))

    def test_archived_binding_direct_orm_blocked(self):
        item = self.create_object()
        item = ObjectService.lifecycle(location=item, user=self.user, version=1, action="close", reason="Synthetic")
        item = ObjectService.lifecycle(location=item, user=self.user, version=item.version, action="archive")
        with self.assertRaises(IntegrityError), transaction.atomic():
            EmployeeAssignment.objects.create(employee=self.actor, location=item)

    def test_legacy_unclassified_identity_preserved(self):
        legacy = Location.objects.create(name="Existing", code="OLD-77", location_type="free-business-value")
        legacy.name = "Existing edit"
        legacy.save()
        legacy.refresh_from_db()
        self.assertEqual(legacy.node_kind, "unclassified")
        self.assertEqual(legacy.location_type, "free-business-value")
        self.assertEqual(legacy.code, "OLD-77")
        self.assertEqual(self.client.get("/api/internal/v1/objects/").data["count"], 0)

    def test_unsupported_scopes_and_geography_fail_closed(self):
        item = self.create_object()
        for scope in ("own", "team", "participating", "org_unit", "legal_entity", "location"):
            user, _ = self.limited(scope)
            self.assertFalse(LocationAccessPolicy.visible(user).exists(), scope)
        with transaction.atomic(), object_write():
            geography = Location.objects.create(name="Synthetic geography", node_kind="geography", timezone="Asia/Novosibirsk")
        user, _ = self.limited("location", {"location": geography})
        self.assertFalse(LocationAccessPolicy.visible(user).exists())
        user, _ = self.limited("location", {"location": item}, ("project.create",))
        from access_control.services import PermissionService
        self.assertFalse(PermissionService.has_permission(employee=user.employee, permission="project.create"))

    def test_distinct_view_edit_grants_and_manage_compatibility(self):
        first = self.create_object(name="First")
        second = self.create_object(name="Second")
        user, assignment = self.limited("location", {"location": first}, ("location.view", "location.manage"))
        self.assertTrue(LocationAccessPolicy.allows(user, "location.edit", first))
        self.assertFalse(LocationAccessPolicy.allows(user, "location.edit", second))
        self.assertTrue(LocationAccessPolicy.allows(user, "location.archive", first))
        self.client.force_authenticate(user)
        self.assertEqual(self.client.patch(f"/api/internal/v1/objects/{second.pk}/", {"version": 1, "name": "No"}, format="json").status_code, 404)
        self.assertEqual(self.client.get("/api/internal/v1/objects/tree/").data["count"], 1)

    def test_invisible_employee_and_inactive_responsibility_rollback(self):
        employee = Employee.objects.create(first_name="Hidden", is_demo=True)
        user, _ = self.limited("global", {}, ("location.create", "location.view", "location.assign_responsible"))
        self.client.force_authenticate(user)
        payload = {"name":"Scoped", "business_type":"office", "timezone":"Asia/Novosibirsk", "manager":str(employee.pk)}
        self.assertEqual(self.client.post("/api/internal/v1/objects/", payload, format="json", HTTP_IDEMPOTENCY_KEY="hidden-person").status_code, 404)
        employee.is_active = False
        employee.save()
        with self.assertRaises(ValidationError):
            self.create_object(manager=employee)
        self.assertEqual(Location.objects.count(), 0)

    def test_cross_object_zone_move_with_links_blocked(self):
        first = self.create_object(name="First")
        second = self.create_object(name="Second")
        zone = ObjectService.zone(parent=first, user=self.user, version=1, name="Zone")
        EmployeeAssignment.objects.create(employee=self.actor, location=zone)
        with self.assertRaises(ValidationError):
            ObjectService.move(location=zone, parent=second, user=self.user, version=1)
        zone.refresh_from_db()
        self.assertEqual(zone.parent, first)

    def test_related_policies_and_counts_and_request_location(self):
        from work_tasks.services import TaskService
        from projects.services import ProjectService
        from projects.models import ProjectTaskLink
        from service_requests.models import ServiceCategory, Service, RequestType
        from service_requests.services import SchemaService, ServiceRequestService
        item = self.create_object()
        zone = ObjectService.zone(parent=item, user=self.user, version=1, name="Zone")
        task = TaskService.create(actor=self.actor, actor_user=self.user, title="Hidden Work", location=zone)
        direct = ProjectService.create(actor=self.actor, actor_user=self.user, name="Direct", location=item)
        participating = ProjectService.create(actor=self.actor, actor_user=self.user, name="Participating")
        ProjectTaskLink.objects.create(project=participating, task=task, linked_by=self.user)
        category = ServiceCategory.objects.create(name="Synthetic")
        service = Service.objects.create(category=category, name="Synthetic")
        request_type = RequestType.objects.create(service=service, name="Synthetic", code="SYNTHETIC-OBJECT-TEST", created_by=self.actor)
        SchemaService.publish(request_type, self.actor, self.user)
        request = ServiceRequestService.create(actor=self.actor, actor_user=self.user, request_type=request_type, subject="Synthetic", payload={}, location=zone)
        self.assertEqual(request.location, zone)
        for kind in ("tasks", "requests", "projects", "participating_projects"):
            self.assertEqual(self.client.get(f"/api/internal/v1/objects/{item.pk}/related/?kind={kind}").data["count"], 1)
        user, _ = self.limited("location", {"location": item}, ("location.view",))
        self.client.force_authenticate(user)
        for kind in ("tasks", "requests", "projects", "participating_projects", "people"):
            result = self.client.get(f"/api/internal/v1/objects/{item.pk}/related/?kind={kind}")
            self.assertEqual(result.status_code, 200, result.data)
            self.assertEqual(result.data["count"], 0, kind)
        response = self.client.post("/api/internal/v1/tasks/", {"title":"Denied", "location":str(zone.pk)}, format="json")
        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(response.data["error"]["code"], "task_permission_denied")

    def test_malformed_filters_are_validation_errors(self):
        for query in ("parent=invalid", "legal_entity=invalid", "business_type=invalid", "business_status=invalid", "archived=invalid"):
            response=self.client.get(f"/api/internal/v1/objects/?{query}")
            self.assertEqual(response.status_code, 400, response.data)

    def test_archived_history_update_allowed_but_assignment_reactivation_denied(self):
        item=self.create_object()
        assignment=EmployeeAssignment.objects.create(employee=self.actor,location=item,status="ended")
        item=ObjectService.lifecycle(location=item,user=self.user,version=1,action="close",reason="Synthetic")
        item=ObjectService.lifecycle(location=item,user=self.user,version=item.version,action="archive")
        EmployeeAssignment.objects.filter(pk=assignment.pk).update(is_primary=False)
        with self.assertRaises(IntegrityError), transaction.atomic():
            EmployeeAssignment.objects.filter(pk=assignment.pk).update(status="active")
        from performance.models import PerformanceFact
        PerformanceFact.objects.create(fact_key="synthetic-history",source_domain="task",source_id=uuid.uuid4(),metric_code="synthetic",employee=self.actor,attribution_role="responsible",occurred_at=item.created_at,location=item)

    def test_responsibility_direct_mutation_and_delete_blocked(self):
        item=self.create_object(manager=self.actor)
        row=LocationResponsibility.objects.get(location=item)
        with self.assertRaises(IntegrityError), transaction.atomic():
            LocationResponsibility.objects.filter(pk=row.pk).update(end_reason="Bypass")
        with self.assertRaises(IntegrityError), transaction.atomic():
            LocationResponsibility.objects.filter(pk=row.pk).delete()

    def test_code_immutable_even_inside_domain_context(self):
        item=self.create_object()
        with self.assertRaises(IntegrityError), transaction.atomic(), object_write():
            Location.objects.filter(pk=item.pk).update(code="CHANGED",version=2)

    def test_hidden_parent_ids_are_masked(self):
        with transaction.atomic(), object_write():
            parent=Location.objects.create(name="Hidden geography",node_kind="geography",timezone="Asia/Novosibirsk")
        legal=LegalEntity.objects.create(name="Synthetic")
        item=self.create_object(parent=parent,legal_entity=legal)
        user,_=self.limited("legal_entity",{"legal_entity":legal})
        self.client.force_authenticate(user)
        result=self.client.get(f"/api/internal/v1/objects/{item.pk}/")
        self.assertIsNone(result.data["parent"])
        self.assertIsNone(result.data["parent_name"])
        self.assertNotIn(str(parent.pk),str(result.data))

    def test_cross_object_move_unused_zone_and_move_targets(self):
        first=self.create_object(name="First")
        second=self.create_object(name="Second")
        zone=ObjectService.zone(parent=first,user=self.user,version=1,name="Zone")
        moved=ObjectService.move(location=zone,parent=second,user=self.user,version=1)
        self.assertEqual(moved.parent,second)
        targets=self.client.get(f"/api/internal/v1/objects/move-targets/?source={zone.pk}")
        self.assertEqual(targets.status_code,200,targets.data)
        self.assertNotIn(str(zone.pk),str(targets.data))

    def test_api_internal_failure_is_sanitized_and_atomic(self):
        with patch("organizations.object_services.AuditService.record",side_effect=RuntimeError("SQL SECRET synthetic")):
            result=self.client.post("/api/internal/v1/objects/",{"name":"Synthetic failure","business_type":"office","timezone":"Asia/Novosibirsk"},format="json",HTTP_IDEMPOTENCY_KEY="synthetic-failure")
        self.assertEqual(result.status_code,500)
        self.assertNotIn("SECRET",str(result.data))
        self.assertEqual(Location.objects.count(),0)

    def test_geography_and_responsible_filters_apply_before_counts(self):
        with transaction.atomic(), object_write():
            geography=Location.objects.create(name="Synthetic geo",node_kind="geography",timezone="Asia/Novosibirsk")
        self.create_object(name="First",parent=geography,manager=self.actor)
        self.create_object(name="Second")
        for query in (f"geography={geography.pk}",f"responsible={self.actor.pk}"):
            result=self.client.get(f"/api/internal/v1/objects/?{query}")
            self.assertEqual(result.data["count"],1,result.data)

    def test_capability_flag_cannot_escape_failed_domain_context(self):
        item=self.create_object()
        try:
            with object_write():
                raise ValidationError("Synthetic failure")
        except ValidationError:
            pass
        with self.assertRaises(IntegrityError), transaction.atomic():
            Location.objects.filter(pk=item.pk).update(name="Bypass after failed command",version=2)


class ObjectsConcurrencyTests(ObjectsSetup, TransactionTestCase):
    def setUp(self):
        self.setup_objects()

    def test_concurrent_same_key_creates_one_object_event(self):
        barrier = threading.Barrier(2)
        def create():
            close_old_connections()
            try:
                user = User.objects.get(pk=self.user.pk)
                barrier.wait(timeout=10)
                item, created = ObjectService.create(user=user, key="concurrent", data={"name": "Concurrent", "business_type": "office", "timezone": "Asia/Novosibirsk"})
                return item.pk, created
            finally:
                connection.close()
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(lambda _: create(), range(2)))
        self.assertEqual(results[0][0], results[1][0])
        self.assertEqual(sum(created for _, created in results), 1)
        self.assertEqual(OutboxEvent.objects.filter(event_type="location.created").count(), 1)

    def test_concurrent_codes_unique(self):
        barrier = threading.Barrier(3)
        def create(index):
            close_old_connections()
            try:
                user = User.objects.get(pk=self.user.pk)
                barrier.wait(timeout=10)
                item, _ = ObjectService.create(user=user, key=str(index), data={"name": f"Concurrent {index}", "business_type": "office", "timezone": "Asia/Novosibirsk"})
                return item.code
            finally:
                connection.close()
        with ThreadPoolExecutor(3) as pool:
            codes = list(pool.map(create, range(3)))
        self.assertEqual(len(set(codes)), 3)

    def test_concurrent_mutual_move_cannot_create_cycle(self):
        item = self.create_object()
        first = ObjectService.zone(parent=item, user=self.user, version=1, name="First")
        item.refresh_from_db()
        second = ObjectService.zone(parent=item, user=self.user, version=item.version, name="Second")
        barrier = threading.Barrier(2)
        def move(pair):
            close_old_connections()
            try:
                source = Location.objects.get(pk=pair[0])
                parent = Location.objects.get(pk=pair[1])
                user = User.objects.get(pk=self.user.pk)
                barrier.wait(timeout=10)
                try:
                    ObjectService.move(location=source, parent=parent, user=user, version=1)
                    return "moved"
                except ValidationError:
                    return "cycle_rejected"
            finally:
                connection.close()
        with ThreadPoolExecutor(2) as pool:
            result=list(pool.map(move, [(first.pk,second.pk),(second.pk,first.pk)]))
        self.assertEqual(sorted(result), ["cycle_rejected", "moved"])

    def test_concurrent_termination_and_assignment_preserve_history(self):
        employee=Employee.objects.create(first_name="Synthetic manager", is_demo=True)
        item=self.create_object()
        barrier=threading.Barrier(2)
        def action(kind):
            close_old_connections()
            try:
                user=User.objects.get(pk=self.user.pk)
                person=Employee.objects.get(pk=employee.pk)
                barrier.wait(timeout=10)
                if kind=="terminate":
                    EmployeeService.terminate(employee=person, actor_user=user)
                    return "terminated"
                try:
                    ObjectService.responsibility(location=Location.objects.get(pk=item.pk), user=user, version=1, role="manager", employee=person)
                    return "assigned"
                except ValidationError:
                    return "rejected"
            finally:
                connection.close()
        with ThreadPoolExecutor(2) as pool:
            list(pool.map(action,["assign","terminate"]))
        employee.refresh_from_db()
        self.assertFalse(employee.is_active)
        self.assertFalse(LocationResponsibility.objects.filter(employee=employee,valid_to__isnull=True).exists())
