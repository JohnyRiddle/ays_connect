from __future__ import annotations

import hashlib
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from access_control.services import PermissionService
from audit.services import AuditService
from events.services import DomainEventService
from .exceptions import TaskBusinessError, TaskValidationError
from .models import (
    ChecklistTemplate, ChecklistTemplateItem, Task, TaskAttachment, TaskChecklist,
    TaskChecklistItem, TaskComment, TaskCommentMention, TaskCommentRevision, TaskWatcher,
)
from .policies import TaskAccessPolicy


class AttachmentScanner:
    def scan(self, uploaded_file):
        return None


class CollaborationService:
    @staticmethod
    def _authorize(*, actor, actor_user, permission, task):
        if actor_user and actor_user.is_superuser:
            return
        if not PermissionService.has_permission(employee=actor, permission="task.view", obj=task) or not PermissionService.has_permission(employee=actor, permission=permission, obj=task):
            raise TaskBusinessError("Недостаточно прав для работы с задачей.", code="task_permission_denied")

    @staticmethod
    def _record(*, entity, task, actor, actor_user, audit_action, event_type, payload=None, correlation_id=None):
        metadata = {"task_id": str(task.pk), "task_number": task.number, **(payload or {})}
        AuditService.record(action=audit_action, entity=entity, actor_user=actor_user, actor_employee=actor, metadata=metadata, correlation_id=correlation_id)
        DomainEventService.publish(event_type=event_type, entity=entity, actor=actor_user, payload={**metadata, "actor_id": str(actor.pk), "occurred_at": timezone.now(), **(payload or {})}, correlation_id=correlation_id)

    @classmethod
    def _validate_mentions(cls, *, actor, actor_user, employees):
        unique = {employee.pk: employee for employee in employees}.values()
        for employee in unique:
            if not employee.is_active:
                raise TaskValidationError("Нельзя упомянуть неактивного сотрудника.", code="task_mention_invalid")
            if not (actor_user and actor_user.is_superuser) and employee.pk != actor.pk and not PermissionService.has_permission(employee=actor, permission="employee.view", obj=employee):
                raise TaskValidationError("Сотрудник недоступен для упоминания.", code="task_mention_invalid")
        return list(unique)

    @classmethod
    @transaction.atomic
    def add_comment(cls, *, task, actor, actor_user, body, mentions=(), is_internal=False, correlation_id=None):
        cls._authorize(actor=actor, actor_user=actor_user, permission="task.comment_internal" if is_internal else "task.comment", task=task)
        body = body.strip()
        if not body:
            raise TaskValidationError("Комментарий не может быть пустым.", code="task_comment_empty")
        employees = cls._validate_mentions(actor=actor, actor_user=actor_user, employees=mentions)
        comment = TaskComment.objects.create(task=task, author=actor, body=body, is_internal=is_internal)
        TaskCommentMention.objects.bulk_create([TaskCommentMention(comment=comment, employee=employee) for employee in employees])
        cls._record(entity=comment, task=task, actor=actor, actor_user=actor_user, audit_action="task.comment.created", event_type="task.comment_added", payload={"comment_id": str(comment.pk), "is_internal": is_internal}, correlation_id=correlation_id)
        for employee in employees:
            if employee.pk != actor.pk:
                DomainEventService.publish(event_type="task.comment_mentioned", entity=comment, actor=actor_user, payload={"task_id": str(task.pk), "task_number": task.number, "comment_id": str(comment.pk), "author_id": str(actor.pk), "mentioned_employee_id": str(employee.pk), "occurred_at": timezone.now()}, correlation_id=correlation_id)
        return comment

    @classmethod
    @transaction.atomic
    def edit_comment(cls, *, comment, actor, actor_user, body, mentions=(), is_internal=None, correlation_id=None):
        task = comment.task
        cls._authorize(actor=actor, actor_user=actor_user, permission="task.comment" if comment.author_id == actor.pk else "task.comment_moderate", task=task)
        if comment.deleted_at:
            raise TaskValidationError("Удалённый комментарий нельзя редактировать.", code="task_comment_deleted")
        body = body.strip()
        if not body:
            raise TaskValidationError("Комментарий не может быть пустым.", code="task_comment_empty")
        employees = cls._validate_mentions(actor=actor, actor_user=actor_user, employees=mentions)
        if is_internal is not None and is_internal != comment.is_internal:
            cls._authorize(actor=actor, actor_user=actor_user, permission="task.comment_internal", task=task)
        old_ids = set(comment.mention_records.values_list("employee_id", flat=True))
        new_ids = {employee.pk for employee in employees}
        TaskCommentRevision.objects.create(comment=comment, body=comment.body, edited_by=actor)
        comment.body, comment.edited_at = body, timezone.now()
        if is_internal is not None: comment.is_internal = is_internal
        comment.save(update_fields=["body", "is_internal", "edited_at", "updated_at"])
        comment.mention_records.exclude(employee_id__in=new_ids).delete()
        new_employees = [employee for employee in employees if employee.pk not in old_ids]
        TaskCommentMention.objects.bulk_create([TaskCommentMention(comment=comment, employee=employee) for employee in new_employees])
        cls._record(entity=comment, task=task, actor=actor, actor_user=actor_user, audit_action="task.comment.updated", event_type="task.comment_updated", payload={"comment_id": str(comment.pk)}, correlation_id=correlation_id)
        for employee in new_employees:
            if employee.pk != actor.pk:
                DomainEventService.publish(event_type="task.comment_mentioned", entity=comment, actor=actor_user, payload={"task_id": str(task.pk), "task_number": task.number, "comment_id": str(comment.pk), "author_id": str(actor.pk), "mentioned_employee_id": str(employee.pk), "occurred_at": timezone.now()}, correlation_id=correlation_id)
        return comment

    @classmethod
    @transaction.atomic
    def delete_comment(cls, *, comment, actor, actor_user, correlation_id=None):
        task = comment.task
        cls._authorize(actor=actor, actor_user=actor_user, permission="task.comment" if comment.author_id == actor.pk else "task.comment_moderate", task=task)
        if not comment.deleted_at:
            comment.deleted_at, comment.deleted_by = timezone.now(), actor
            comment.save(update_fields=["deleted_at", "deleted_by", "updated_at"])
            cls._record(entity=comment, task=task, actor=actor, actor_user=actor_user, audit_action="task.comment.deleted", event_type="task.comment_deleted", payload={"comment_id": str(comment.pk)}, correlation_id=correlation_id)
        return comment

    @classmethod
    def _validate_file(cls, uploaded_file):
        if not uploaded_file or uploaded_file.size <= 0:
            raise TaskValidationError("Файл пуст.", code="task_attachment_empty")
        if uploaded_file.size > settings.TASK_ATTACHMENT_MAX_SIZE:
            raise TaskValidationError("Файл превышает допустимый размер.", code="task_attachment_too_large")
        content_type = (uploaded_file.content_type or "application/octet-stream").lower()
        if content_type not in settings.TASK_ATTACHMENT_ALLOWED_TYPES:
            raise TaskValidationError("Тип файла запрещён политикой безопасности.", code="task_attachment_type_forbidden")
        original = Path(uploaded_file.name).name.strip().replace("\x00", "")
        if not original or len(original) > 255:
            raise TaskValidationError("Некорректное имя файла.", code="task_attachment_filename_invalid")
        header = uploaded_file.read(8)
        uploaded_file.seek(0)
        if header.startswith((b"MZ", b"\x7fELF", b"#!")):
            raise TaskValidationError("Исполняемые файлы запрещены.", code="task_attachment_type_forbidden")
        digest = hashlib.sha256()
        for chunk in uploaded_file.chunks():
            digest.update(chunk)
        uploaded_file.seek(0)
        return original, content_type, digest.hexdigest()

    @classmethod
    def add_attachment(cls, *, task, actor, actor_user, uploaded_file, scanner=None, correlation_id=None):
        cls._authorize(actor=actor, actor_user=actor_user, permission="task.attachment_add", task=task)
        original, content_type, checksum = cls._validate_file(uploaded_file)
        (scanner or AttachmentScanner()).scan(uploaded_file)
        attachment = TaskAttachment(task=task, original_filename=original, content_type=content_type, size=uploaded_file.size, checksum=checksum, uploaded_by=actor)
        stored_name = None
        try:
            with transaction.atomic():
                attachment.file.save("file", uploaded_file, save=False)
                stored_name = attachment.file.name
                attachment.save()
                cls._record(entity=attachment, task=task, actor=actor, actor_user=actor_user, audit_action="task.attachment.added", event_type="task.attachment_added", payload={"attachment_id": str(attachment.pk), "filename": original, "content_type": content_type, "size": attachment.size, "checksum": checksum, "uploaded_by": str(actor.pk)}, correlation_id=correlation_id)
        except Exception:
            if stored_name:
                attachment.file.storage.delete(stored_name)
            raise
        return attachment

    @classmethod
    @transaction.atomic
    def delete_attachment(cls, *, attachment, actor, actor_user, correlation_id=None):
        cls._authorize(actor=actor, actor_user=actor_user, permission="task.attachment_delete", task=attachment.task)
        if not attachment.deleted_at:
            attachment.deleted_at, attachment.deleted_by = timezone.now(), actor
            attachment.save(update_fields=["deleted_at", "deleted_by"])
            cls._record(entity=attachment, task=attachment.task, actor=actor, actor_user=actor_user, audit_action="task.attachment.deleted", event_type="task.attachment_deleted", payload={"attachment_id": str(attachment.pk)}, correlation_id=correlation_id)
        return attachment

    @classmethod
    @transaction.atomic
    def add_watcher(cls, *, task, employee, actor, actor_user, correlation_id=None):
        permission = "task.watch" if employee.pk == actor.pk else "task.watcher_manage"
        cls._authorize(actor=actor, actor_user=actor_user, permission=permission, task=task)
        if not employee.is_active:
            raise TaskValidationError("Нельзя добавить неактивного наблюдателя.", code="task_watcher_invalid")
        watcher = TaskWatcher.objects.select_for_update().filter(task=task, employee=employee, removed_at__isnull=True).first()
        if watcher:
            return watcher
        watcher = TaskWatcher.objects.create(task=task, employee=employee, added_by=actor)
        cls._record(entity=watcher, task=task, actor=actor, actor_user=actor_user, audit_action="task.watcher.added", event_type="task.watcher_added", payload={"employee_id": str(employee.pk)}, correlation_id=correlation_id)
        return watcher

    @classmethod
    @transaction.atomic
    def remove_watcher(cls, *, task, employee, actor, actor_user, correlation_id=None):
        permission = "task.watch" if employee.pk == actor.pk else "task.watcher_manage"
        cls._authorize(actor=actor, actor_user=actor_user, permission=permission, task=task)
        watcher = TaskWatcher.objects.select_for_update().get(task=task, employee=employee, removed_at__isnull=True)
        watcher.removed_at, watcher.removed_by = timezone.now(), actor
        watcher.save(update_fields=["removed_at", "removed_by"])
        cls._record(entity=watcher, task=task, actor=actor, actor_user=actor_user, audit_action="task.watcher.removed", event_type="task.watcher_removed", payload={"employee_id": str(employee.pk)}, correlation_id=correlation_id)
        return watcher


class ChecklistService:
    @staticmethod
    def _authorize_task(actor, actor_user, permission, task):
        CollaborationService._authorize(actor=actor, actor_user=actor_user, permission=permission, task=task)

    @staticmethod
    def _authorize_template(actor, actor_user, permission):
        if actor_user and actor_user.is_superuser:
            return
        if not TaskAccessPolicy.allows(employee=actor, permission=permission):
            raise TaskBusinessError("Недостаточно прав для шаблонов чек-листов.", code="task_permission_denied")

    @classmethod
    @transaction.atomic
    def create_template(cls, *, actor, actor_user, name, description="", items=(), correlation_id=None):
        cls._authorize_template(actor, actor_user, "checklist_template.manage")
        template = ChecklistTemplate.objects.create(name=name.strip(), description=description, created_by=actor)
        for index, item in enumerate(items, start=1):
            ChecklistTemplateItem.objects.create(template=template, text=item["text"].strip(), position=item.get("position", index), required=item.get("required", False))
        AuditService.record(action="checklist_template.created", entity=template, actor_user=actor_user, actor_employee=actor, correlation_id=correlation_id)
        return template

    @classmethod
    @transaction.atomic
    def update_template(cls, *, template, actor, actor_user, name=None, description=None, is_active=None, correlation_id=None):
        cls._authorize_template(actor, actor_user, "checklist_template.manage")
        action = "checklist_template.deactivated" if is_active is False and template.is_active else "checklist_template.updated"
        if name is not None: template.name = name.strip()
        if description is not None: template.description = description
        if is_active is not None: template.is_active = is_active
        template.save()
        AuditService.record(action=action, entity=template, actor_user=actor_user, actor_employee=actor, correlation_id=correlation_id)
        return template

    @classmethod
    @transaction.atomic
    def create_manual(cls, *, task, actor, actor_user, name, items=(), correlation_id=None):
        cls._authorize_task(actor, actor_user, "task.checklist_manage", task)
        checklist = TaskChecklist.objects.create(task=task, name=name.strip(), created_by=actor)
        for index, item in enumerate(items, start=1):
            TaskChecklistItem.objects.create(checklist=checklist, text=item["text"].strip(), position=item.get("position", index), required=item.get("required", False))
        CollaborationService._record(entity=checklist, task=task, actor=actor, actor_user=actor_user, audit_action="task.checklist.created", event_type="task.checklist_added", payload={"checklist_id": str(checklist.pk)}, correlation_id=correlation_id)
        return checklist

    @classmethod
    @transaction.atomic
    def from_template(cls, *, task, template, actor, actor_user, correlation_id=None):
        cls._authorize_task(actor, actor_user, "task.checklist_manage", task)
        if not template.is_active:
            raise TaskValidationError("Шаблон чек-листа деактивирован.", code="checklist_template_inactive")
        checklist = TaskChecklist.objects.create(task=task, name=template.name, source_template=template, created_by=actor)
        TaskChecklistItem.objects.bulk_create([
            TaskChecklistItem(checklist=checklist, text=item.text, position=item.position, required=item.required)
            for item in template.items.order_by("position", "id")
        ])
        CollaborationService._record(entity=checklist, task=task, actor=actor, actor_user=actor_user, audit_action="task.checklist.created", event_type="task.checklist_added", payload={"checklist_id": str(checklist.pk), "template_id": str(template.pk)}, correlation_id=correlation_id)
        return checklist

    @classmethod
    @transaction.atomic
    def add_item(cls, *, checklist, actor, actor_user, text, position, required=False, correlation_id=None):
        cls._authorize_task(actor, actor_user, "task.checklist_manage", checklist.task)
        if checklist.removed_at:
            raise TaskValidationError("Чек-лист удалён.", code="task_checklist_removed")
        item = TaskChecklistItem.objects.create(checklist=checklist, text=text.strip(), position=position, required=required)
        CollaborationService._record(entity=item, task=checklist.task, actor=actor, actor_user=actor_user, audit_action="task.checklist_item.created", event_type="task.checklist_item_added", payload={"checklist_id": str(checklist.pk), "item_id": str(item.pk)}, correlation_id=correlation_id)
        return item

    @classmethod
    @transaction.atomic
    def update_item(cls, *, item, actor, actor_user, correlation_id=None, **changes):
        cls._authorize_task(actor, actor_user, "task.checklist_manage", item.checklist.task)
        for field in ("text", "position", "required", "comment"):
            if field in changes:
                setattr(item, field, changes[field])
        item.save()
        CollaborationService._record(entity=item, task=item.checklist.task, actor=actor, actor_user=actor_user, audit_action="task.checklist_item.updated", event_type="task.checklist_item_updated", payload={"item_id": str(item.pk)}, correlation_id=correlation_id)
        return item

    @classmethod
    @transaction.atomic
    def set_completed(cls, *, item, actor, actor_user, completed, comment=None, correlation_id=None):
        task = Task.objects.select_for_update().get(pk=item.checklist.task_id)
        cls._authorize_task(actor, actor_user, "task.checklist_complete", task)
        item = TaskChecklistItem.objects.select_for_update().get(pk=item.pk, checklist__task=task, checklist__removed_at__isnull=True)
        item.is_completed = completed
        item.completed_by = actor if completed else None
        item.completed_at = timezone.now() if completed else None
        if comment is not None: item.comment = comment
        item.save(update_fields=["is_completed", "completed_by", "completed_at", "comment", "updated_at"])
        suffix = "completed" if completed else "uncompleted"
        CollaborationService._record(entity=item, task=task, actor=actor, actor_user=actor_user, audit_action=f"task.checklist_item.{suffix}", event_type=f"task.checklist_item_{suffix}", payload={"checklist_id": str(item.checklist_id), "item_id": str(item.pk)}, correlation_id=correlation_id)
        return item

    @classmethod
    @transaction.atomic
    def remove_checklist(cls, *, checklist, actor, actor_user, correlation_id=None):
        cls._authorize_task(actor, actor_user, "task.checklist_manage", checklist.task)
        if not checklist.removed_at:
            checklist.removed_at, checklist.removed_by = timezone.now(), actor
            checklist.save(update_fields=["removed_at", "removed_by"])
            CollaborationService._record(entity=checklist, task=checklist.task, actor=actor, actor_user=actor_user, audit_action="task.checklist.removed", event_type="task.checklist_removed", payload={"checklist_id": str(checklist.pk)}, correlation_id=correlation_id)
        return checklist
