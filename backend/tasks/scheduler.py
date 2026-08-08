import calendar
from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone

from checklists.models import ChecklistRun, ChecklistTemplate
from .models import RecurrenceRule, Task, TaskHistory


def advance(moment, frequency, interval=1):
    interval=max(int(interval or 1),1)
    if frequency in {"daily","after_completion"}: return moment+timedelta(days=interval)
    if frequency=="weekly": return moment+timedelta(weeks=interval)
    if frequency=="monthly":
        month_index=moment.month-1+interval
        year=moment.year+month_index//12
        month=month_index%12+1
        day=min(moment.day,calendar.monthrange(year,month)[1])
        return moment.replace(year=year,month=month,day=day)
    return moment+timedelta(days=interval)


def _checklist_assignee(template):
    if template.default_assignee_id: return template.default_assignee
    if template.facility.manager_id: return template.facility.manager
    employee=template.facility.employees.filter(user__isnull=False,status="active").select_related("user").first()
    return employee.user if employee else None


@transaction.atomic
def run_due_schedules(now=None):
    now=now or timezone.now()
    counters={"tasks":0,"checklists":0,"skipped":0}
    rules=RecurrenceRule.objects.select_for_update(of=("self",)).select_related("task_template").filter(is_active=True,next_run_at__lte=now)
    for rule in rules:
        template=rule.task_template
        scheduled_for=rule.next_run_at
        duration=max(template.initial_deadline-template.created_at,timedelta(minutes=15))
        task,created=Task.objects.get_or_create(
            recurrence_rule=rule,scheduled_for=scheduled_for,
            defaults={
                "title":template.title,"description":template.description,"creator":template.creator,"assignee":template.assignee,
                "facility":template.facility,"department":template.department,"zone":template.zone,"category":template.category,
                "priority":template.priority,"criticality":template.criticality,"complexity":template.complexity,
                "estimated_minutes":template.estimated_minutes,"planned_start":scheduled_for,"initial_deadline":scheduled_for+duration,
                "deadline":scheduled_for+duration,"acceptance_criteria":template.acceptance_criteria,"requires_review":template.requires_review,
                "requires_comment":template.requires_comment,"requires_photo":template.requires_photo,"requires_file":template.requires_file,
                "source":Task.Source.SCHEDULE,"status":Task.Status.ASSIGNED,"is_demo":template.is_demo,
            },
        )
        if created:
            task.collaborators.set(template.collaborators.all()); task.observers.set(template.observers.all()); task.approvers.set(template.approvers.all())
            TaskHistory.objects.create(task=task,actor=template.creator,action="created_from_schedule",to_status=task.status,details={"scheduled_for":scheduled_for.isoformat()})
            counters["tasks"]+=1
        else: counters["skipped"]+=1
        rule.next_run_at=advance(scheduled_for,rule.frequency,rule.interval); rule.save(update_fields=["next_run_at"])

    templates=ChecklistTemplate.objects.select_for_update(of=("self",)).select_related("facility","default_assignee","facility__manager").filter(is_active=True,next_run_at__lte=now)
    for template in templates:
        scheduled_for=template.next_run_at
        assignee=_checklist_assignee(template)
        if assignee:
            due_at=scheduled_for
            if template.deadline_time:
                due_at=timezone.make_aware(datetime.combine(timezone.localdate(scheduled_for),template.deadline_time),timezone.get_current_timezone())
                if due_at<scheduled_for: due_at+=timedelta(days=1)
            _,created=ChecklistRun.objects.get_or_create(template=template,scheduled_for=scheduled_for,defaults={"assignee":assignee,"facility":template.facility,"due_at":due_at,"is_demo":template.is_demo})
            counters["checklists" if created else "skipped"]+=1
        else: counters["skipped"]+=1
        if template.frequency==ChecklistTemplate.Frequency.ONCE:
            template.is_active=False; template.next_run_at=None; template.save(update_fields=["is_active","next_run_at"])
        else:
            template.next_run_at=advance(scheduled_for,template.frequency); template.save(update_fields=["next_run_at"])
    return counters
