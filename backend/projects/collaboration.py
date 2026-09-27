from django.db import transaction
from django.utils import timezone

from audit.services import AuditService
from config.attachments import AttachmentScanner, AttachmentSecurityError, validate_attachment
from events.services import DomainEventService

from .models import ProjectAttachment, ProjectComment, ProjectCommentMention
from .policies import ProjectAccessPolicy
from .services import ProjectBusinessError, ProjectService


class ProjectCollaborationService:
    @staticmethod
    def authorize(actor, actor_user, permission, project):
        ProjectService.authorize(actor,actor_user,"project.view",project)
        ProjectService.authorize(actor,actor_user,permission,project)

    @staticmethod
    def record(project,entity,actor,actor_user,action,correlation_id=None,**payload):
        AuditService.record(action=action,entity=entity,actor_user=actor_user,actor_employee=actor,
            metadata={"project_id":str(project.pk),**payload},correlation_id=correlation_id)
        DomainEventService.publish(event_type=action,entity=entity,actor=actor_user,
            payload={"project_id":str(project.pk),**payload},correlation_id=correlation_id)

    @classmethod
    @transaction.atomic
    def comment(cls, *, project, actor, actor_user, body, mentions=(), correlation_id=None):
        cls.authorize(actor,actor_user,"project.comment",project)
        if not body.strip():raise ProjectBusinessError("Комментарий не может быть пустым.")
        unique={employee.pk:employee for employee in mentions}
        for employee in unique.values():
            if not employee.is_active or not employee.user_id or not ProjectAccessPolicy.allows(employee,"project.view",project):
                raise ProjectBusinessError("Упомянутый сотрудник недоступен в проекте.","project_mention_forbidden")
        item=ProjectComment.objects.create(project=project,author=actor,body=body.strip())
        ProjectCommentMention.objects.bulk_create([ProjectCommentMention(comment=item,employee=e) for e in unique.values()])
        cls.record(project,item,actor,actor_user,"project.comment_added",correlation_id,comment_id=str(item.pk))
        ProjectService.notify(project,actor_user,[e.pk for e in unique.values() if e.pk!=actor.pk],
            "PROJECT_COMMENT_MENTIONED",correlation_id,comment_id=str(item.pk))
        return item

    @classmethod
    @transaction.atomic
    def delete_comment(cls, *, comment, actor, actor_user, correlation_id=None):
        cls.authorize(actor,actor_user,"project.comment",comment.project)
        if comment.author_id!=actor.pk and not (actor_user and actor_user.is_superuser):
            raise ProjectBusinessError("Удалить комментарий может только автор.","project_comment_forbidden")
        if comment.deleted_at:return comment
        comment.deleted_at=timezone.now();comment.deleted_by=actor
        comment.save(update_fields=["deleted_at","deleted_by","updated_at"])
        cls.record(comment.project,comment,actor,actor_user,"project.comment_deleted",correlation_id,comment_id=str(comment.pk))
        return comment

    @classmethod
    def add_attachment(cls, *, project, actor, actor_user, uploaded_file, scanner=None, correlation_id=None):
        cls.authorize(actor,actor_user,"project.attachment_add",project)
        try:
            original,content_type,checksum=validate_attachment(uploaded_file)
        except AttachmentSecurityError as exc:
            raise ProjectBusinessError(str(exc),f"project_{exc.code}") from exc
        (scanner or AttachmentScanner()).scan(uploaded_file)
        item=ProjectAttachment(project=project,original_filename=original,content_type=content_type,
                               size=uploaded_file.size,checksum=checksum,uploaded_by=actor)
        stored_name=None
        try:
            with transaction.atomic():
                item.file.save("file",uploaded_file,save=False)
                stored_name=item.file.name
                item.save()
                cls.record(project,item,actor,actor_user,"project.attachment_added",correlation_id,
                    attachment_id=str(item.pk),size=item.size,checksum=checksum)
        except Exception:
            if stored_name:item.file.storage.delete(stored_name)
            raise
        return item

    @classmethod
    @transaction.atomic
    def delete_attachment(cls, *, attachment, actor, actor_user, correlation_id=None):
        cls.authorize(actor,actor_user,"project.attachment_delete",attachment.project)
        if attachment.deleted_at:return attachment
        attachment.deleted_at=timezone.now();attachment.deleted_by=actor
        attachment.save(update_fields=["deleted_at","deleted_by"])
        cls.record(attachment.project,attachment,actor,actor_user,"project.attachment_deleted",correlation_id,
            attachment_id=str(attachment.pk))
        return attachment
