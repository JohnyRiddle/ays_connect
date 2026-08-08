from datetime import timedelta

from django.utils import timezone

from notifications.models import Notification
from tasks.models import Task, TaskHistory


def notify_once(*, recipient, notification_type, title, message, entity_type, entity_id, priority=Notification.Priority.INFO):
    notification, _ = Notification.objects.get_or_create(
        recipient=recipient, notification_type=notification_type,
        entity_type=entity_type, entity_id=entity_id, title=title,
        defaults={"message": message, "priority": priority, "telegram_status": "pending", "is_demo": recipient.is_demo},
    )
    return notification


def provision_course_assignment(assignment, *, create_task=False):
    user = assignment.employee.user
    if not user:
        return assignment
    notify_once(recipient=user, notification_type=Notification.Type.COURSE_ASSIGNED,
                title="Назначен курс", message=f"«{assignment.course.title}». Срок: {assignment.due_at:%d.%m.%Y}" if assignment.due_at else f"«{assignment.course.title}». Без срока.",
                entity_type="CourseAssignment", entity_id=assignment.id)
    if create_task and not assignment.related_task_id:
        deadline = assignment.due_at or timezone.now() + timedelta(days=7)
        task = Task.objects.create(title=f"Пройти курс «{assignment.course.title}»", description=assignment.course.short_description or assignment.course.description,
                                   creator=assignment.assigned_by, assignee=user, department=assignment.employee.department,
                                   priority=Task.Priority.HIGH if assignment.is_mandatory else Task.Priority.NORMAL,
                                   initial_deadline=deadline, deadline=deadline, acceptance_criteria="Успешно завершить курс и итоговый тест",
                                   requires_review=False, source=Task.Source.TRAINING, status=Task.Status.ASSIGNED, is_demo=user.is_demo)
        TaskHistory.objects.create(task=task, actor=assignment.assigned_by, action="created_from_training", to_status=task.status, details={"assignment_id": assignment.id})
        assignment.related_task = task
        assignment.save(update_fields=["related_task"])
    return assignment


def complete_linked_task(assignment, *, actor):
    task = assignment.related_task
    if not task or task.status in {Task.Status.CLOSED, Task.Status.COMPLETED, Task.Status.CANCELLED}:
        return
    old = task.status
    task.status = Task.Status.CLOSED
    task.completed_at = timezone.now()
    task.result_text = "Закрыта автоматически после завершения обучения"
    task.save(update_fields=["status", "completed_at", "result_text", "updated_at"])
    TaskHistory.objects.create(task=task, actor=actor, action="closed_by_training", from_status=old, to_status=task.status, details={"assignment_id": assignment.id})


def notify_course_completed(assignment):
    user = assignment.employee.user
    if user:
        notify_once(recipient=user, notification_type=Notification.Type.COURSE_COMPLETED, title="Курс завершён",
                    message=f"Курс «{assignment.course.title}» успешно завершён.", entity_type="CourseAssignment", entity_id=assignment.id)
