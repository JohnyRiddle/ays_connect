from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from events.services import DomainEventService
from projects.models import ProjectMilestone, ProjectMilestoneDueNotice, ProjectStatus
from employees.models import Employee


def process_due_milestones(limit=100, now=None):
    now = now or timezone.now()
    emitted = 0
    ids = ProjectMilestone.objects.filter(due_at__lte=now, confirmed_at__isnull=True,
        responsible__is_active=True, project__is_archived=False,
        ).exclude(responsible__status__in=[Employee.Status.ARCHIVED, Employee.Status.SUSPENDED,
            Employee.Status.DISMISSED, Employee.Status.TERMINATED]).filter(
        project__status__in=[ProjectStatus.DRAFT, ProjectStatus.ACTIVE, ProjectStatus.ON_HOLD]).order_by("due_at", "id").values_list("pk", flat=True)[:limit]
    for milestone_id in ids:
        with transaction.atomic():
            milestone = ProjectMilestone.objects.select_for_update(of=("self",)).select_related("project", "responsible").get(pk=milestone_id)
            if not milestone.due_at or milestone.due_at > now or milestone.confirmed_at or not milestone.responsible_id:
                continue
            if not milestone.responsible.is_active or milestone.responsible.status in {
                Employee.Status.ARCHIVED, Employee.Status.SUSPENDED, Employee.Status.DISMISSED, Employee.Status.TERMINATED}:
                continue
            if milestone.project.is_archived or milestone.project.status not in {ProjectStatus.DRAFT, ProjectStatus.ACTIVE, ProjectStatus.ON_HOLD}:
                continue
            notice, created = ProjectMilestoneDueNotice.objects.get_or_create(
                milestone=milestone, due_at=milestone.due_at, recipient=milestone.responsible)
            if not created:
                continue
            DomainEventService.publish(event_type="notification.requested", entity=milestone.project,
                payload={"reason":"PROJECT_MILESTONE_DUE", "recipient_employee_id":str(milestone.responsible_id),
                         "project_id":str(milestone.project_id), "project_number":milestone.project.number,
                         "milestone_id":str(milestone.pk), "milestone_name":milestone.name,
                         "due_at":milestone.due_at.isoformat(), "notice_id":str(notice.pk)})
            emitted += 1
    return emitted


class Command(BaseCommand):
    help = "Emit idempotent due milestone notifications into the transactional Outbox."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        if options["limit"] < 1 or options["limit"] > 1000:
            raise ValueError("limit must be between 1 and 1000")
        self.stdout.write(f"emitted={process_due_milestones(options['limit'])}")
