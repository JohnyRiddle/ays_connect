import hashlib
import os
import tempfile
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import User
from access_control.models import EmployeeRole, Permission, Role, RolePermission, Scope
from audit.models import AuditEvent
from employees.models import Employee
from events.models import OutboxEvent
from organizations.models import LegalEntity, OrgUnit

from .activity import ServiceRequestActivitySelector
from .collaboration import RequestCollaborationService
from .exceptions import RequestBusinessError
from .models import (CollaborationVisibility, FieldType, RequestFieldDefinition,
                     RequestType, Service, ServiceCategory,
                     ServiceRequestAttachment, ServiceRequestComment,
                     ServiceRequestWatcher)
from .policies import ServiceRequestAccessPolicy
from .services import SchemaService, ServiceRequestService


class RequestCollaborationTests(TestCase):
    def setUp(self):
        self.admin_user=User.objects.create_superuser(username="collab-admin",password="x")
        self.admin=Employee.objects.create(user=self.admin_user,first_name="Admin")
        self.le=LegalEntity.objects.create(name="Collab LE");self.unit=OrgUnit.objects.create(name="Collab Unit",legal_entity=self.le)
        self.requester_user=User.objects.create_user(username="requester",email="requester@collab.test");self.requester=Employee.objects.create(user=self.requester_user,first_name="Requester",legal_entity=self.le,org_unit=self.unit)
        self.agent_user=User.objects.create_user(username="agent",email="agent@collab.test");self.agent=Employee.objects.create(user=self.agent_user,first_name="Agent",legal_entity=self.le,org_unit=self.unit)
        category=ServiceCategory.objects.create(name="IT");service=Service.objects.create(category=category,name="Support");self.rt=RequestType.objects.create(service=service,name="Help",code="COLLAB_HELP",created_by=self.admin)
        RequestFieldDefinition.objects.create(request_type=self.rt,key="details",label="Details",field_type=FieldType.TEXT,required=True);SchemaService.publish(self.rt,self.admin,self.admin_user)
        self.request=ServiceRequestService.create(actor=self.admin,actor_user=self.admin_user,request_type=self.rt,requester=self.requester,subject="Help",payload={"details":"x"})
        self._grant(self.requester,"requester",[("request.view",Scope.OWN),("request.comment",Scope.OWN),("request.attachment_add",Scope.OWN),("request.attachment_delete",Scope.OWN),("request.watch",Scope.OWN)])
        self._grant(self.agent,"agent",[(code,Scope.GLOBAL) for code in ("request.view","request.comment","request.comment_internal","request.comment_moderate","request.attachment_add","request.attachment_internal","request.attachment_delete","request.watch","request.watcher_manage")])
        self.media=tempfile.TemporaryDirectory();self.override=override_settings(MEDIA_ROOT=self.media.name);self.override.enable()
    def tearDown(self):self.override.disable();self.media.cleanup();super().tearDown()
    def _grant(self,employee,code,permissions):
        role=Role.objects.create(code=code,name=code)
        for permission,scope in permissions:
            p,_=Permission.objects.get_or_create(code=permission,defaults={"name":permission});RolePermission.objects.create(role=role,permission=p,scope=scope)
        EmployeeRole.objects.create(employee=employee,role=role)

    def test_public_internal_revision_soft_delete_and_version_independence(self):
        version=self.request.version
        public=RequestCollaborationService.add_comment(request=self.request,actor=self.requester,actor_user=self.requester_user,body=" Public ",mentions=[self.requester])
        internal=RequestCollaborationService.add_comment(request=self.request,actor=self.agent,actor_user=self.agent_user,body="Internal",visibility=CollaborationVisibility.INTERNAL)
        public=RequestCollaborationService.edit_comment(comment=public,actor=self.requester,actor_user=self.requester_user,body="Edited",mentions=[])
        self.assertEqual(public.revisions.get().body,"Public");RequestCollaborationService.delete_comment(comment=public,actor=self.requester,actor_user=self.requester_user);public.refresh_from_db();self.assertIsNotNone(public.deleted_at)
        self.request.refresh_from_db();self.assertEqual(self.request.version,version);self.assertEqual(internal.visibility,"internal")
        with self.assertRaises(RequestBusinessError):RequestCollaborationService.add_comment(request=self.request,actor=self.requester,actor_user=self.requester_user,body=" ")
        with self.assertRaises(RequestBusinessError):RequestCollaborationService.add_comment(request=self.request,actor=self.requester,actor_user=self.requester_user,body="Escalate",visibility=CollaborationVisibility.INTERNAL)

    def test_mentions_validate_visibility_and_emit_only_for_new(self):
        with self.assertRaises(RequestBusinessError):RequestCollaborationService.add_comment(request=self.request,actor=self.agent,actor_user=self.agent_user,body="Secret",visibility=CollaborationVisibility.INTERNAL,mentions=[self.requester])
        comment=RequestCollaborationService.add_comment(request=self.request,actor=self.requester,actor_user=self.requester_user,body="Me",mentions=[self.requester,self.requester])
        self.assertEqual(comment.mention_records.count(),1);before=OutboxEvent.objects.filter(event_type="request.comment_mentioned",entity_id=str(comment.pk)).count()
        RequestCollaborationService.edit_comment(comment=comment,actor=self.requester,actor_user=self.requester_user,body="Still me",mentions=[self.requester]);self.assertEqual(OutboxEvent.objects.filter(event_type="request.comment_mentioned",entity_id=str(comment.pk)).count(),before)
        self.requester.is_active=False;self.requester.save(update_fields=["is_active"])
        with self.assertRaises(RequestBusinessError):RequestCollaborationService.add_comment(request=self.request,actor=self.agent,actor_user=self.agent_user,body="Inactive",mentions=[self.requester])

    def test_attachment_security_checksum_path_soft_delete_and_cleanup(self):
        content=b"request attachment";attachment=RequestCollaborationService.add_attachment(request=self.request,actor=self.requester,actor_user=self.requester_user,uploaded_file=SimpleUploadedFile("../report.txt",content,content_type="text/plain"))
        self.assertEqual(attachment.original_filename,"report.txt");self.assertEqual(attachment.checksum,hashlib.sha256(content).hexdigest());self.assertIn(str(self.request.pk),attachment.file.name);self.assertNotIn("report.txt",attachment.file.name)
        RequestCollaborationService.delete_attachment(attachment=attachment,actor=self.requester,actor_user=self.requester_user);attachment.refresh_from_db();self.assertIsNotNone(attachment.deleted_at)
        with self.assertRaises(RequestBusinessError):RequestCollaborationService.add_attachment(request=self.request,actor=self.requester,actor_user=self.requester_user,uploaded_file=SimpleUploadedFile("evil.txt",b"MZpayload",content_type="text/plain"))
        with override_settings(ATTACHMENT_MAX_SIZE=3):
            with self.assertRaises(RequestBusinessError):RequestCollaborationService.add_attachment(request=self.request,actor=self.requester,actor_user=self.requester_user,uploaded_file=SimpleUploadedFile("large.txt",b"four",content_type="text/plain"))
        upload=SimpleUploadedFile("rollback.txt",b"safe",content_type="text/plain")
        with patch("service_requests.collaboration.DomainEventService.publish",side_effect=RuntimeError("outbox")):
            with self.assertRaises(RuntimeError):RequestCollaborationService.add_attachment(request=self.request,actor=self.requester,actor_user=self.requester_user,uploaded_file=upload)
        self.assertFalse(ServiceRequestAttachment.objects.filter(original_filename="rollback.txt").exists());self.assertFalse(any(files for _,_,files in os.walk(self.media.name) if "rollback" in " ".join(files)))

    def test_watch_participation_without_internal_escalation(self):
        watcher_user=User.objects.create_user(username="watch-only",email="watch@collab.test");watcher_employee=Employee.objects.create(user=watcher_user,first_name="Watcher")
        self._grant(watcher_employee,"watch-only-role",[("request.view",Scope.PARTICIPATING)])
        self.assertFalse(ServiceRequestAccessPolicy.allows(employee=watcher_employee,permission="request.view",request=self.request))
        watcher=RequestCollaborationService.add_watcher(request=self.request,employee=watcher_employee,actor=self.agent,actor_user=self.agent_user);duplicate=RequestCollaborationService.add_watcher(request=self.request,employee=watcher_employee,actor=self.agent,actor_user=self.agent_user);self.assertEqual(watcher.pk,duplicate.pk)
        self.assertTrue(ServiceRequestAccessPolicy.allows(employee=watcher_employee,permission="request.view",request=self.request));self.assertFalse(ServiceRequestAccessPolicy.can_view_internal(employee=watcher_employee,request=self.request))
        RequestCollaborationService.remove_watcher(request=self.request,employee=watcher_employee,actor=self.agent,actor_user=self.agent_user);self.assertFalse(ServiceRequestAccessPolicy.allows(employee=watcher_employee,permission="request.view",request=self.request))

    def test_atomic_comment_and_watcher_rollback(self):
        with patch("service_requests.collaboration.AuditService.record",side_effect=RuntimeError("audit")):
            with self.assertRaises(RuntimeError):RequestCollaborationService.add_comment(request=self.request,actor=self.requester,actor_user=self.requester_user,body="rollback")
        self.assertFalse(ServiceRequestComment.objects.filter(body="rollback").exists())
        with patch("service_requests.collaboration.DomainEventService.publish",side_effect=RuntimeError("outbox")):
            with self.assertRaises(RuntimeError):RequestCollaborationService.add_watcher(request=self.request,employee=self.agent,actor=self.agent,actor_user=self.agent_user)
        self.assertFalse(ServiceRequestWatcher.objects.filter(request=self.request,employee=self.agent,removed_at__isnull=True).exists())

    def test_requester_api_hides_internal_comment_attachment_activity_and_summary(self):
        internal=RequestCollaborationService.add_comment(request=self.request,actor=self.agent,actor_user=self.agent_user,body="Secret",visibility=CollaborationVisibility.INTERNAL)
        attachment=RequestCollaborationService.add_attachment(request=self.request,actor=self.agent,actor_user=self.agent_user,uploaded_file=SimpleUploadedFile("secret.txt",b"secret",content_type="text/plain"),visibility=CollaborationVisibility.INTERNAL)
        client=APIClient();client.force_authenticate(self.requester_user);base=f"/api/internal/v1/requests/{self.request.pk}"
        comments=client.get(f"{base}/comments/");self.assertEqual(comments.status_code,200);self.assertEqual(comments.data,[])
        self.assertEqual(client.post(f"{base}/comments/",{"body":"escalate","visibility":"internal"},format="json").status_code,400)
        self.assertEqual(client.patch(f"{base}/comments/{internal.pk}/",{"body":"steal"},format="json").status_code,404)
        self.assertEqual(client.delete(f"{base}/comments/{internal.pk}/").status_code,404)
        self.assertEqual(client.get(f"{base}/attachments/{attachment.pk}/download/").status_code,404)
        activity=client.get(f"{base}/activity/").data;self.assertFalse(any(row["type"].startswith("request.comment") or row["type"].startswith("request.attachment") for row in activity["results"]))
        detail=client.get(f"{base}/").data;self.assertNotIn("internal_comments_count",detail["collaboration"]);self.assertEqual(detail["collaboration"]["attachments_count"],0)

    def test_cancelled_request_collaboration_is_read_only(self):
        self.request.status="cancelled";self.request.save(update_fields=["status"])
        with self.assertRaises(RequestBusinessError):RequestCollaborationService.add_comment(request=self.request,actor=self.requester,actor_user=self.requester_user,body="late")
        with self.assertRaises(RequestBusinessError):RequestCollaborationService.add_attachment(request=self.request,actor=self.requester,actor_user=self.requester_user,uploaded_file=SimpleUploadedFile("late.txt",b"late",content_type="text/plain"))

    def test_activity_stable_pagination_and_safe_payload(self):
        for i in range(4):RequestCollaborationService.add_comment(request=self.request,actor=self.agent,actor_user=self.agent_user,body=f"Body {i}",visibility=CollaborationVisibility.INTERNAL if i==0 else CollaborationVisibility.PUBLIC)
        one=ServiceRequestActivitySelector.page(request=self.request,employee=self.agent,page=1,page_size=2);two=ServiceRequestActivitySelector.page(request=self.request,employee=self.agent,page=2,page_size=2);ids=[x["id"] for x in one["results"]+two["results"]];self.assertEqual(len(ids),len(set(ids)));self.assertTrue(all("Body" not in str(row["data"]) for row in one["results"]+two["results"]))
