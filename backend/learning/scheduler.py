from datetime import timedelta

from django.utils import timezone

from knowledge_base.models import KnowledgeMaterial, MaterialAcknowledgmentAssignment
from notifications.models import Notification
from .integrations import notify_once
from .models import Certificate, CourseAssignment
from .automation import assign_courses_by_audience, reassign_expired_certificates


def process_learning_deadlines(now=None):
    now = now or timezone.now()
    counters = {"courses_overdue": 0, "due_reminders": 0, "ack_overdue": 0, "certificates_expiring": 0, "certificates_expired": 0, "audience_assignments": 0, "repeat_assignments": 0, "materials_need_update": 0}
    counters["audience_assignments"] = assign_courses_by_audience(now)
    active = CourseAssignment.objects.select_related("employee__user", "course").filter(due_at__isnull=False).exclude(status__in=[CourseAssignment.Status.COMPLETED, CourseAssignment.Status.CANCELLED, CourseAssignment.Status.EXPIRED])
    for assignment in active:
        user = assignment.employee.user
        if assignment.due_at < now:
            if assignment.status != CourseAssignment.Status.OVERDUE:
                assignment.status = CourseAssignment.Status.OVERDUE; assignment.save(update_fields=["status"]); counters["courses_overdue"] += 1
            if user: notify_once(recipient=user, notification_type=Notification.Type.COURSE_OVERDUE, title="Курс просрочен", message=f"Истёк срок курса «{assignment.course.title}».", entity_type="CourseAssignment", entity_id=assignment.id, priority=Notification.Priority.WARNING)
        elif assignment.due_at <= now + timedelta(days=3) and user:
            _, created = Notification.objects.get_or_create(recipient=user, notification_type=Notification.Type.COURSE_DUE_SOON, entity_type="CourseAssignment", entity_id=assignment.id, title="Срок курса приближается", defaults={"message": f"Завершите «{assignment.course.title}» до {assignment.due_at:%d.%m.%Y}.", "priority": Notification.Priority.WARNING})
            counters["due_reminders"] += int(created)
    acknowledgments = MaterialAcknowledgmentAssignment.objects.select_related("employee__user", "version__material").filter(due_at__lt=now).exclude(status__in=[MaterialAcknowledgmentAssignment.Status.ACKNOWLEDGED, MaterialAcknowledgmentAssignment.Status.CANCELLED, MaterialAcknowledgmentAssignment.Status.OVERDUE])
    for item in acknowledgments:
        item.status = item.Status.OVERDUE; item.save(update_fields=["status"]); counters["ack_overdue"] += 1
        if item.employee.user: notify_once(recipient=item.employee.user, notification_type=Notification.Type.MATERIAL_ACK_OVERDUE, title="Ознакомление просрочено", message=f"Не подтверждено ознакомление с «{item.version.material.title}».", entity_type="MaterialAcknowledgmentAssignment", entity_id=item.id, priority=Notification.Priority.WARNING)
    for certificate in Certificate.objects.select_related("employee__user", "course").filter(expires_at__isnull=False).exclude(status=Certificate.Status.REVOKED):
        if certificate.expires_at < now:
            if certificate.status != Certificate.Status.EXPIRED: certificate.status = Certificate.Status.EXPIRED; certificate.save(update_fields=["status"]); counters["certificates_expired"] += 1
            kind, title = Notification.Type.CERTIFICATE_EXPIRED, "Сертификат истёк"
        elif certificate.expires_at <= now + timedelta(days=30):
            if certificate.status != Certificate.Status.EXPIRING: certificate.status = Certificate.Status.EXPIRING; certificate.save(update_fields=["status"]); counters["certificates_expiring"] += 1
            kind, title = Notification.Type.CERTIFICATE_EXPIRING, "Сертификат скоро истечёт"
        else:
            if certificate.status != Certificate.Status.ACTIVE: certificate.status = Certificate.Status.ACTIVE; certificate.save(update_fields=["status"])
            continue
        if certificate.employee.user: notify_once(recipient=certificate.employee.user, notification_type=kind, title=title, message=f"Сертификат по курсу «{certificate.course.title}»: {certificate.expires_at:%d.%m.%Y}.", entity_type="Certificate", entity_id=certificate.id, priority=Notification.Priority.WARNING)
    counters["repeat_assignments"] = reassign_expired_certificates(now)
    counters["materials_need_update"] = KnowledgeMaterial.objects.filter(
        review_at__lt=now,
        status=KnowledgeMaterial.Status.PUBLISHED,
    ).update(status=KnowledgeMaterial.Status.NEEDS_UPDATE)
    return counters
