from django.db import IntegrityError, transaction
from django.utils import timezone

from audit.services import AuditService
from config.attachments import AttachmentScanner, AttachmentSecurityError, validate_attachment
from events.services import DomainEventService

from .exceptions import RequestBusinessError
from .models import (CollaborationVisibility, RequestStatus,
                     ServiceRequestAttachment, ServiceRequestComment,
                     ServiceRequestCommentMention,
                     ServiceRequestCommentRevision, ServiceRequestWatcher)
from .policies import ServiceRequestAccessPolicy


class RequestCollaborationService:
    @staticmethod
    def _authorize(*, request, actor, actor_user, permission):
        if actor_user and actor_user.is_superuser:return
        if not ServiceRequestAccessPolicy.allows(employee=actor,permission="request.view",request=request) or not ServiceRequestAccessPolicy.allows(employee=actor,permission=permission,request=request):
            raise RequestBusinessError("Insufficient collaboration permission.",code="request_permission_denied")
    @staticmethod
    def _record(*,entity,request,actor,actor_user,audit_action,event_type,payload=None):
        metadata={"request_id":str(request.pk),"request_number":request.number,**(payload or {})}
        AuditService.record(action=audit_action,entity=entity,actor_user=actor_user,actor_employee=actor,metadata=metadata)
        DomainEventService.publish(event_type=event_type,entity=entity,actor=actor_user,payload={**metadata,"actor_id":str(actor.pk)})
    @classmethod
    def _can_internal(cls,request,employee):
        return ServiceRequestAccessPolicy.can_view_internal(employee=employee,request=request)
    @classmethod
    def _mentions(cls,*,request,employees,visibility):
        unique=list({employee.pk:employee for employee in employees}.values())
        for employee in unique:
            if not employee.is_active:raise RequestBusinessError("Inactive employee cannot be mentioned.",code="request_mention_invalid")
            if not ServiceRequestAccessPolicy.allows(employee=employee,permission="request.view",request=request):raise RequestBusinessError("Mentioned employee cannot view request.",code="request_mention_invalid")
            if visibility==CollaborationVisibility.INTERNAL and not cls._can_internal(request,employee):raise RequestBusinessError("Mentioned employee cannot view internal note.",code="request_mention_invalid")
        return unique
    @classmethod
    @transaction.atomic
    def add_comment(cls,*,request,actor,actor_user,body,visibility=CollaborationVisibility.PUBLIC,mentions=()):
        if request.status==RequestStatus.CANCELLED and not actor_user.is_superuser:raise RequestBusinessError("Cancelled request is read-only.",code="request_collaboration_read_only")
        permission="request.comment_internal" if visibility==CollaborationVisibility.INTERNAL else "request.comment"
        cls._authorize(request=request,actor=actor,actor_user=actor_user,permission=permission)
        body=body.strip()
        if not body:raise RequestBusinessError("Comment cannot be empty.",code="request_comment_empty")
        employees=cls._mentions(request=request,employees=mentions,visibility=visibility)
        comment=ServiceRequestComment.objects.create(request=request,author=actor,body=body,visibility=visibility)
        ServiceRequestCommentMention.objects.bulk_create([ServiceRequestCommentMention(comment=comment,employee=e) for e in employees])
        cls._record(entity=comment,request=request,actor=actor,actor_user=actor_user,audit_action="request.comment.created",event_type="request.comment_added",payload={"comment_id":str(comment.pk),"visibility":visibility})
        for employee in employees:
            if employee.pk!=actor.pk:DomainEventService.publish(event_type="request.comment_mentioned",entity=comment,actor=actor_user,payload={"request_id":str(request.pk),"comment_id":str(comment.pk),"mentioned_employee_id":str(employee.pk),"visibility":visibility})
        return comment
    @classmethod
    @transaction.atomic
    def edit_comment(cls,*,comment,actor,actor_user,body,mentions=()):
        request=comment.request
        if request.status==RequestStatus.CANCELLED and not actor_user.is_superuser:raise RequestBusinessError("Cancelled request is read-only.",code="request_collaboration_read_only")
        permission="request.comment" if comment.author_id==actor.pk else "request.comment_moderate"
        cls._authorize(request=request,actor=actor,actor_user=actor_user,permission=permission)
        if comment.visibility==CollaborationVisibility.INTERNAL:cls._authorize(request=request,actor=actor,actor_user=actor_user,permission="request.comment_internal")
        if comment.deleted_at:raise RequestBusinessError("Deleted comment cannot be edited.",code="request_comment_deleted")
        body=body.strip()
        if not body:raise RequestBusinessError("Comment cannot be empty.",code="request_comment_empty")
        employees=cls._mentions(request=request,employees=mentions,visibility=comment.visibility);old_ids=set(comment.mention_records.values_list("employee_id",flat=True));new_ids={e.pk for e in employees}
        ServiceRequestCommentRevision.objects.create(comment=comment,body=comment.body,edited_by=actor);comment.body=body;comment.edited_at=timezone.now();comment.save(update_fields=["body","edited_at","updated_at"])
        comment.mention_records.exclude(employee_id__in=new_ids).delete();new=[e for e in employees if e.pk not in old_ids];ServiceRequestCommentMention.objects.bulk_create([ServiceRequestCommentMention(comment=comment,employee=e) for e in new])
        cls._record(entity=comment,request=request,actor=actor,actor_user=actor_user,audit_action="request.comment.updated",event_type="request.comment_updated",payload={"comment_id":str(comment.pk),"visibility":comment.visibility})
        for employee in new:
            if employee.pk!=actor.pk:DomainEventService.publish(event_type="request.comment_mentioned",entity=comment,actor=actor_user,payload={"request_id":str(request.pk),"comment_id":str(comment.pk),"mentioned_employee_id":str(employee.pk),"visibility":comment.visibility})
        return comment
    @classmethod
    @transaction.atomic
    def delete_comment(cls,*,comment,actor,actor_user):
        permission="request.comment" if comment.author_id==actor.pk else "request.comment_moderate";cls._authorize(request=comment.request,actor=actor,actor_user=actor_user,permission=permission)
        if comment.visibility==CollaborationVisibility.INTERNAL:cls._authorize(request=comment.request,actor=actor,actor_user=actor_user,permission="request.comment_internal")
        if not comment.deleted_at:comment.deleted_at=timezone.now();comment.deleted_by=actor;comment.save(update_fields=["deleted_at","deleted_by","updated_at"]);cls._record(entity=comment,request=comment.request,actor=actor,actor_user=actor_user,audit_action="request.comment.deleted",event_type="request.comment_deleted",payload={"comment_id":str(comment.pk),"visibility":comment.visibility})
        return comment
    @classmethod
    def add_attachment(cls,*,request,actor,actor_user,uploaded_file,visibility=CollaborationVisibility.PUBLIC,scanner=None):
        if request.status in {RequestStatus.CLOSED,RequestStatus.CANCELLED}:raise RequestBusinessError("Attachments are read-only in final state.",code="request_collaboration_read_only")
        cls._authorize(request=request,actor=actor,actor_user=actor_user,permission="request.attachment_add")
        if visibility==CollaborationVisibility.INTERNAL:cls._authorize(request=request,actor=actor,actor_user=actor_user,permission="request.attachment_internal")
        try:original,content_type,checksum=validate_attachment(uploaded_file)
        except AttachmentSecurityError as exc:raise RequestBusinessError(str(exc),code=f"request_{exc.code}") from exc
        (scanner or AttachmentScanner()).scan(uploaded_file);attachment=ServiceRequestAttachment(request=request,original_filename=original,content_type=content_type,size=uploaded_file.size,checksum=checksum,uploaded_by=actor,visibility=visibility);stored=None
        try:
            with transaction.atomic():
                attachment.file.save("file",uploaded_file,save=False);stored=attachment.file.name;attachment.save();cls._record(entity=attachment,request=request,actor=actor,actor_user=actor_user,audit_action="request.attachment.added",event_type="request.attachment_added",payload={"attachment_id":str(attachment.pk),"filename":original,"content_type":content_type,"size":attachment.size,"checksum":checksum,"visibility":visibility})
        except Exception:
            if stored:attachment.file.storage.delete(stored)
            raise
        return attachment
    @classmethod
    @transaction.atomic
    def delete_attachment(cls,*,attachment,actor,actor_user):
        cls._authorize(request=attachment.request,actor=actor,actor_user=actor_user,permission="request.attachment_delete")
        if attachment.visibility==CollaborationVisibility.INTERNAL:cls._authorize(request=attachment.request,actor=actor,actor_user=actor_user,permission="request.attachment_internal")
        if not attachment.deleted_at:attachment.deleted_at=timezone.now();attachment.deleted_by=actor;attachment.save(update_fields=["deleted_at","deleted_by"]);cls._record(entity=attachment,request=attachment.request,actor=actor,actor_user=actor_user,audit_action="request.attachment.deleted",event_type="request.attachment_deleted",payload={"attachment_id":str(attachment.pk),"visibility":attachment.visibility})
        return attachment
    @classmethod
    @transaction.atomic
    def add_watcher(cls,*,request,employee,actor,actor_user,system=False):
        if not system:cls._authorize(request=request,actor=actor,actor_user=actor_user,permission="request.watch" if employee.pk==actor.pk else "request.watcher_manage")
        if not employee.is_active:raise RequestBusinessError("Inactive employee cannot watch.",code="request_watcher_invalid")
        watcher=ServiceRequestWatcher.objects.filter(request=request,employee=employee,removed_at__isnull=True).first()
        if watcher:return watcher
        try:
            with transaction.atomic():watcher=ServiceRequestWatcher.objects.create(request=request,employee=employee,added_by=actor)
        except IntegrityError:
            return ServiceRequestWatcher.objects.get(request=request,employee=employee,removed_at__isnull=True)
        cls._record(entity=watcher,request=request,actor=actor,actor_user=actor_user,audit_action="request.watcher.added",event_type="request.watcher_added",payload={"employee_id":str(employee.pk)});return watcher
    @classmethod
    @transaction.atomic
    def remove_watcher(cls,*,request,employee,actor,actor_user):
        cls._authorize(request=request,actor=actor,actor_user=actor_user,permission="request.watch" if employee.pk==actor.pk else "request.watcher_manage")
        watcher=ServiceRequestWatcher.objects.select_for_update().get(request=request,employee=employee,removed_at__isnull=True);watcher.removed_at=timezone.now();watcher.removed_by=actor;watcher.save(update_fields=["removed_at","removed_by"]);cls._record(entity=watcher,request=request,actor=actor,actor_user=actor_user,audit_action="request.watcher.removed",event_type="request.watcher_removed",payload={"employee_id":str(employee.pk)});return watcher
