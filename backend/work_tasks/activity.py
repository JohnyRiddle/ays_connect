from django.db.models import Q

from audit.models import AuditEvent
from access_control.services import PermissionService


class TaskActivitySelector:
    TYPE_MAP = {
        "task.comment.created": "task.comment_added",
        "task.comment.updated": "task.comment_updated",
        "task.comment.deleted": "task.comment_deleted",
        "task.attachment.added": "task.attachment_added",
        "task.attachment.deleted": "task.attachment_deleted",
        "task.watcher.added": "task.watcher_added",
        "task.watcher.removed": "task.watcher_removed",
        "task.checklist.created": "task.checklist_added",
        "task.checklist_item.completed": "task.checklist_item_completed",
        "task.checklist_item.uncompleted": "task.checklist_item_uncompleted",
    }

    @classmethod
    def page(cls, *, task, employee, page=1, page_size=25):
        can_internal = PermissionService.has_permission(employee=employee, permission="task.comment_internal", obj=task)
        queryset = AuditEvent.objects.select_related("actor_employee").filter(
            Q(entity_type="Task", entity_id=str(task.pk)) | Q(metadata__task_id=str(task.pk))
        )
        if not can_internal:
            queryset = queryset.exclude(metadata__is_internal=True)
        queryset = queryset.order_by("-created_at", "-id")
        page = max(int(page), 1)
        page_size = min(max(int(page_size), 1), 100)
        total = queryset.count()
        rows = queryset[(page - 1) * page_size:page * page_size]
        results = []
        for row in rows:
            actor = row.actor_employee
            data = dict(row.metadata or {})
            data.pop("task_id", None)
            data.pop("task_number", None)
            if row.action == "task.comment.deleted":
                data = {"message": "Комментарий удалён", **{k: v for k, v in data.items() if k != "body"}}
            results.append({
                "id": str(row.pk),
                "type": cls.TYPE_MAP.get(row.action, row.action if row.action.startswith("task.") else f"task.{row.action}"),
                "timestamp": row.created_at,
                "actor": {"id": str(actor.pk), "display_name": actor.display_name} if actor else None,
                "data": data,
            })
        return {"count": total, "page": page, "page_size": page_size, "results": results}
