import hashlib
import os
import tempfile
from datetime import timedelta
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from access_control.models import EmployeeRole, Permission, Role, RolePermission, Scope
from accounts.models import User
from audit.models import AuditEvent
from employees.models import AssignmentTarget, Employee
from events.models import OutboxEvent
from organizations.models import LegalEntity, OrgUnit
from .activity import TaskActivitySelector
from .collaboration import ChecklistService, CollaborationService
from .exceptions import TaskValidationError
from .models import AcceptancePolicy, ChecklistTemplateItem, Task, TaskAttachment, TaskCommentMention, TaskStatus, TaskWatcher, WaitingReason
from .policies import TaskAccessPolicy
from .services import TaskService


class CollaborationTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username="collab-admin", email="collab-admin@test.local", password="pass")
        self.le = LegalEntity.objects.create(name="Collab LE")
        self.unit = OrgUnit.objects.create(name="Collab Unit", legal_entity=self.le)
        self.actor = Employee.objects.create(user=self.user, first_name="Анна", last_name="Автор", legal_entity=self.le, org_unit=self.unit)
        self.other = Employee.objects.create(first_name="Иван", last_name="Упомянутый", legal_entity=self.le, org_unit=self.unit)
        self.target = AssignmentTarget.objects.create(target_type=AssignmentTarget.Type.EMPLOYEE, employee=self.actor)
        self.task = TaskService.create(actor=self.actor, actor_user=self.user, title="Collaboration", responsible_target=self.target, legal_entity=self.le, org_unit=self.unit)

    def start_task(self, acceptance_policy=AcceptancePolicy.NONE):
        self.task.acceptance_policy = acceptance_policy
        self.task.save(update_fields=["acceptance_policy"])
        self.task = TaskService.publish(task=self.task, actor=self.actor, actor_user=self.user, version=self.task.version)
        self.task = TaskService.start(task=self.task, actor=self.actor, actor_user=self.user, version=self.task.version)
        return self.task


class CommentMentionTests(CollaborationTestCase):
    def test_comment_edit_revision_mentions_and_soft_delete(self):
        comment = CollaborationService.add_comment(task=self.task, actor=self.actor, actor_user=self.user, body="Первый текст", mentions=[self.other, self.other])
        self.assertEqual(comment.mention_records.count(), 1)
        self.assertEqual(OutboxEvent.objects.filter(event_type="task.comment_mentioned", entity_id=str(comment.pk)).count(), 1)
        comment = CollaborationService.edit_comment(comment=comment, actor=self.actor, actor_user=self.user, body="Новый текст", mentions=[self.other])
        self.assertEqual(comment.revisions.get().body, "Первый текст")
        self.assertEqual(OutboxEvent.objects.filter(event_type="task.comment_mentioned", entity_id=str(comment.pk)).count(), 1)
        CollaborationService.delete_comment(comment=comment, actor=self.actor, actor_user=self.user)
        comment.refresh_from_db()
        self.assertIsNotNone(comment.deleted_at)
        self.assertEqual(comment.body, "Новый текст")

    def test_empty_comment_and_inactive_mention_are_rejected(self):
        with self.assertRaises(TaskValidationError):
            CollaborationService.add_comment(task=self.task, actor=self.actor, actor_user=self.user, body="  ")
        self.other.is_active = False
        self.other.save(update_fields=["is_active"])
        with self.assertRaises(TaskValidationError):
            CollaborationService.add_comment(task=self.task, actor=self.actor, actor_user=self.user, body="Mention", mentions=[self.other])

    def test_comment_mentions_roll_back_with_event_failure(self):
        with patch("work_tasks.collaboration.DomainEventService.publish", side_effect=RuntimeError("outbox")):
            with self.assertRaises(RuntimeError):
                CollaborationService.add_comment(task=self.task, actor=self.actor, actor_user=self.user, body="Rollback", mentions=[self.other])
        self.assertFalse(self.task.production_comments.filter(body="Rollback").exists())
        self.assertFalse(TaskCommentMention.objects.filter(comment__body="Rollback").exists())


class AttachmentTests(CollaborationTestCase):
    def setUp(self):
        super().setUp()
        self.media = tempfile.TemporaryDirectory()
        self.override = override_settings(MEDIA_ROOT=self.media.name)
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        self.media.cleanup()
        super().tearDown()

    def test_attachment_metadata_checksum_safe_path_and_soft_delete(self):
        content = b"production attachment"
        upload = SimpleUploadedFile("../report.txt", content, content_type="text/plain")
        attachment = CollaborationService.add_attachment(task=self.task, actor=self.actor, actor_user=self.user, uploaded_file=upload)
        self.assertEqual(attachment.original_filename, "report.txt")
        self.assertEqual(attachment.checksum, hashlib.sha256(content).hexdigest())
        self.assertIn(str(self.task.pk), attachment.file.name)
        self.assertNotIn("report.txt", attachment.file.name)
        self.assertTrue(attachment.file.storage.exists(attachment.file.name))
        CollaborationService.delete_attachment(attachment=attachment, actor=self.actor, actor_user=self.user)
        attachment.refresh_from_db()
        self.assertIsNotNone(attachment.deleted_at)
        self.assertTrue(attachment.file.storage.exists(attachment.file.name))

    def test_forbidden_mime_and_storage_cleanup_on_db_transaction_failure(self):
        bad = SimpleUploadedFile("payload.exe", b"MZ", content_type="application/x-msdownload")
        with self.assertRaises(TaskValidationError):
            CollaborationService.add_attachment(task=self.task, actor=self.actor, actor_user=self.user, uploaded_file=bad)
        upload = SimpleUploadedFile("safe.txt", b"safe", content_type="text/plain")
        with patch("work_tasks.collaboration.DomainEventService.publish", side_effect=RuntimeError("outbox")):
            with self.assertRaises(RuntimeError):
                CollaborationService.add_attachment(task=self.task, actor=self.actor, actor_user=self.user, uploaded_file=upload)
        self.assertFalse(TaskAttachment.objects.filter(original_filename="safe.txt").exists())
        files = [name for _, _, names in os.walk(self.media.name) for name in names]
        self.assertEqual(files, [])


class WatcherPermissionTests(TestCase):
    def setUp(self):
        self.le = LegalEntity.objects.create(name="Watcher LE")
        self.unit = OrgUnit.objects.create(name="Watcher Unit", legal_entity=self.le)
        self.admin_user = User.objects.create_superuser(username="watch-admin", email="watch-admin@test.local")
        self.admin = Employee.objects.create(user=self.admin_user, first_name="Admin")
        self.viewer_user = User.objects.create_user(username="watcher", email="watcher@test.local")
        self.viewer = Employee.objects.create(user=self.viewer_user, first_name="Watcher")
        self.owner = Employee.objects.create(first_name="Owner")
        target = AssignmentTarget.objects.create(target_type=AssignmentTarget.Type.EMPLOYEE, employee=self.owner)
        self.task = Task.objects.create(number="TASK-700001", title="Foreign", author=self.owner, responsible_target=target, responsible_employee=self.owner, created_by=self.admin_user, updated_by=self.admin_user)
        role = Role.objects.create(code="watch-view", name="Watch View")
        view = Permission.objects.create(code="task.view", name="View")
        RolePermission.objects.create(role=role, permission=view, scope=Scope.PARTICIPATING)
        EmployeeRole.objects.create(employee=self.viewer, role=role)

    def test_active_watcher_is_participant_and_unwatch_removes_access(self):
        self.assertFalse(TaskAccessPolicy.allows(employee=self.viewer, permission="task.view", task=self.task))
        watcher = CollaborationService.add_watcher(task=self.task, employee=self.viewer, actor=self.admin, actor_user=self.admin_user)
        self.assertTrue(TaskAccessPolicy.allows(employee=self.viewer, permission="task.view", task=self.task))
        duplicate = CollaborationService.add_watcher(task=self.task, employee=self.viewer, actor=self.admin, actor_user=self.admin_user)
        self.assertEqual(duplicate.pk, watcher.pk)
        CollaborationService.remove_watcher(task=self.task, employee=self.viewer, actor=self.admin, actor_user=self.admin_user)
        self.assertFalse(TaskAccessPolicy.allows(employee=self.viewer, permission="task.view", task=self.task))


class ChecklistTests(CollaborationTestCase):
    def test_template_snapshot_is_immutable(self):
        template = ChecklistService.create_template(actor=self.actor, actor_user=self.user, name="Template", items=[{"text": "Old", "required": True}])
        first = ChecklistService.from_template(task=self.task, template=template, actor=self.actor, actor_user=self.user)
        item = template.items.get()
        item.text = "New"
        item.save(update_fields=["text"])
        second_task = TaskService.create(actor=self.actor, actor_user=self.user, title="Second", responsible_target=self.target)
        second = ChecklistService.from_template(task=second_task, template=template, actor=self.actor, actor_user=self.user)
        self.assertEqual(first.items.get().text, "Old")
        self.assertEqual(second.items.get().text, "New")

    def test_required_item_blocks_completion_until_completed(self):
        self.start_task()
        checklist = ChecklistService.create_manual(task=self.task, actor=self.actor, actor_user=self.user, name="Required", items=[{"text": "Do", "required": True}])
        with self.assertRaises(TaskValidationError) as caught:
            TaskService.complete(task=self.task, actor=self.actor, actor_user=self.user, version=self.task.version)
        self.assertEqual(caught.exception.code, "task_checklist_incomplete")
        ChecklistService.set_completed(item=checklist.items.get(), actor=self.actor, actor_user=self.user, completed=True)
        self.task = TaskService.complete(task=self.task, actor=self.actor, actor_user=self.user, version=self.task.version)
        self.assertEqual(self.task.status, TaskStatus.COMPLETED)

    def test_complete_and_uncomplete_item_audit_and_events(self):
        checklist = ChecklistService.create_manual(task=self.task, actor=self.actor, actor_user=self.user, name="Manual", items=[{"text": "One"}])
        item = ChecklistService.set_completed(item=checklist.items.get(), actor=self.actor, actor_user=self.user, completed=True)
        self.assertEqual(item.completed_by, self.actor)
        self.assertIsNotNone(item.completed_at)
        item = ChecklistService.set_completed(item=item, actor=self.actor, actor_user=self.user, completed=False)
        self.assertIsNone(item.completed_by)
        self.assertTrue(AuditEvent.objects.filter(action="task.checklist_item.uncompleted").exists())
        self.assertTrue(OutboxEvent.objects.filter(event_type="task.checklist_item_uncompleted").exists())


class ActivityAndNestedSecurityTests(CollaborationTestCase):
    def test_activity_is_stably_paginated_and_hides_internal_without_permission(self):
        for index in range(4):
            CollaborationService.add_comment(task=self.task, actor=self.actor, actor_user=self.user, body=f"Comment {index}", is_internal=index == 0)
        role = Role.objects.create(code="activity-view", name="Activity")
        view = Permission.objects.create(code="task.view", name="View")
        RolePermission.objects.create(role=role, permission=view, scope=Scope.PARTICIPATING)
        EmployeeRole.objects.create(employee=self.actor, role=role)
        first = TaskActivitySelector.page(task=self.task, employee=self.actor, page=1, page_size=2)
        second = TaskActivitySelector.page(task=self.task, employee=self.actor, page=2, page_size=2)
        ids = [row["id"] for row in first["results"] + second["results"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(not row["data"].get("is_internal") for row in first["results"] + second["results"]))

    def test_attachment_nested_idor_returns_404(self):
        viewer_user = User.objects.create_user(username="idor", email="idor@test.local")
        viewer = Employee.objects.create(user=viewer_user, first_name="IDOR")
        own_target = AssignmentTarget.objects.create(target_type=AssignmentTarget.Type.EMPLOYEE, employee=viewer)
        own = Task.objects.create(number="TASK-800001", title="Own", author=viewer, responsible_target=own_target, responsible_employee=viewer, created_by=viewer_user, updated_by=viewer_user)
        role = Role.objects.create(code="idor-view", name="IDOR View")
        permission = Permission.objects.create(code="task.view", name="View")
        RolePermission.objects.create(role=role, permission=permission, scope=Scope.PARTICIPATING)
        EmployeeRole.objects.create(employee=viewer, role=role)
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            attachment = CollaborationService.add_attachment(task=self.task, actor=self.actor, actor_user=self.user, uploaded_file=SimpleUploadedFile("secret.txt", b"secret", content_type="text/plain"))
            client = APIClient(); client.force_authenticate(viewer_user)
            self.assertEqual(client.get(f"/api/internal/v1/tasks/{self.task.pk}/attachments/{attachment.pk}/download/").status_code, 404)
            self.assertEqual(client.get(f"/api/internal/v1/tasks/{own.pk}/").status_code, 200)


class CollaborationApiTests(CollaborationTestCase):
    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.media = tempfile.TemporaryDirectory()
        self.override = override_settings(MEDIA_ROOT=self.media.name)
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        self.media.cleanup()
        super().tearDown()

    def test_nested_collaboration_and_template_endpoints(self):
        base = f"/api/internal/v1/tasks/{self.task.pk}"
        response = self.client.post(f"{base}/comments/", {"body": "API comment", "mentions": [str(self.other.pk)]}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        comment_id = response.data["id"]
        response = self.client.patch(f"{base}/comments/{comment_id}/", {"body": "Edited"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)

        response = self.client.post(f"{base}/attachments/", {"file": SimpleUploadedFile("api.txt", b"api", content_type="text/plain")}, format="multipart")
        self.assertEqual(response.status_code, 201, response.data)
        attachment_id = response.data["id"]
        download = self.client.get(f"{base}/attachments/{attachment_id}/download/")
        self.assertEqual(download.status_code, 200)

        self.assertEqual(self.client.post(f"{base}/watch/", {}, format="json").status_code, 201)
        self.assertEqual(self.client.get(f"{base}/watchers/").status_code, 200)

        response = self.client.post(f"{base}/checklists/", {"name": "API checklist", "items": [{"text": "Step", "position": 1, "required": True}]}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        checklist_id, item_id = response.data["id"], response.data["items"][0]["id"]
        self.assertEqual(self.client.post(f"{base}/checklists/{checklist_id}/items/{item_id}/complete/", {}, format="json").status_code, 200)
        self.assertEqual(self.client.get(f"{base}/activity/?page_size=5").status_code, 200)

        response = self.client.post("/api/internal/v1/checklist-templates/", {"name": "API template", "items": [{"text": "Template step", "position": 1, "required": False}]}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(self.client.get("/api/internal/v1/checklist-templates/").status_code, 200)
        # Release the file handle without Response.close(), which emits
        # request_finished and closes PostgreSQL inside TestCase.atomic().
        for closer in download._resource_closers:
            closer()
        download._resource_closers.clear()
