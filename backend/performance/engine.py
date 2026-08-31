from datetime import timedelta
from decimal import Decimal
from statistics import median

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from service_requests.models import RequestStatus, ServiceRequest
from sla.models import MetricType, SLAMetricInstance, SLAMetricStatus
from work_tasks.models import Task, TaskReviewHistory, TaskStatus

from .models import CALCULATION_VERSION, AttributionRole, PerformanceAggregate, PerformanceFact, SubjectType
from .registry import METRICS


TERMINAL_REQUESTS = (RequestStatus.RESOLVED, RequestStatus.CLOSED, RequestStatus.CANCELLED)
ACTIVE_TASKS = (TaskStatus.OPEN, TaskStatus.IN_PROGRESS, TaskStatus.WAITING, TaskStatus.REVIEW)


def _seconds(start, end):
    return max(0, int((end - start).total_seconds())) if start and end else 0


def _employee_at(history, current, at, assignment_type=None):
    rows = list(history.order_by("created_at"))
    if assignment_type:
        rows = [row for row in rows if row.assignment_type == assignment_type]
    previous = rows[0].old_employee if rows else current
    for row in rows:
        if row.created_at > at:
            break
        previous = row.new_employee
    return previous


def _assignment_started_at(history, employee, at, default, assignment_type=None):
    rows = history.filter(created_at__lte=at, new_employee=employee).order_by("-created_at")
    if assignment_type: rows = rows.filter(assignment_type=assignment_type)
    latest = rows.first()
    return latest.created_at if latest else default


def _deadline_at(task, at):
    due = task.initial_due_at
    for change in task.deadline_history.all():
        if change.created_at <= at: due = change.new_due_at
    return due if due is not None else task.due_at


def _waiting_seconds(periods, start, end):
    total = 0
    for period in periods:
        overlap_start = max(period.started_at, start); overlap_end = min(period.ended_at or end, end)
        if overlap_start < overlap_end: total += _seconds(overlap_start, overlap_end)
    return total


def _fact(source, metric, employee, role, occurred_at, value=1, sample_size=1, suffix=""):
    if not employee or not occurred_at:
        return None
    key = f"{source._meta.app_label}:{source.pk}:{metric}:{employee.pk}:{role}:{suffix}"
    return PerformanceFact(
        fact_key=key, source_domain=source._meta.app_label, source_id=source.pk,
        metric_code=metric, employee=employee, attribution_role=role,
        occurred_at=occurred_at, value=Decimal(str(value)), sample_size=sample_size,
        org_unit_id=getattr(source, "org_unit_id", None) or employee.org_unit_id,
        legal_entity_id=getattr(source, "legal_entity_id", None) or employee.legal_entity_id,
        location_id=getattr(source, "location_id", None) or employee.primary_location_id,
    )


def build_facts(period_from, period_to):
    """Rebuild a closed [from, to) slice. Canonical tables remain untouched."""
    facts = []
    task_qs = Task.objects.filter(
        Q(created_at__gte=period_from, created_at__lt=period_to)
        | Q(completed_at__gte=period_from, completed_at__lt=period_to)
        | (Q(waiting_periods__started_at__lt=period_to) & (Q(waiting_periods__ended_at__gt=period_from) | Q(waiting_periods__ended_at__isnull=True)))
    ).select_related("author", "responsible_employee", "executor_employee").prefetch_related(
        "assignment_history", "waiting_periods", "deadline_history", "review_history", "status_history"
    ).distinct()
    for task in task_qs:
        if period_from <= task.created_at < period_to:
            facts.append(_fact(task, "tasks_created", task.author, AttributionRole.REQUESTER, task.created_at))
        if task.completed_at and period_from <= task.completed_at < period_to:
            employee = _employee_at(task.assignment_history, task.executor_employee or task.responsible_employee, task.completed_at, "executor")
            employee = employee or _employee_at(task.assignment_history, task.responsible_employee, task.completed_at, "responsible")
            cycle_seconds = max(0, _seconds(task.created_at, task.completed_at) - _waiting_seconds(task.waiting_periods.all(), task.created_at, task.completed_at))
            due_at_completion = _deadline_at(task, task.completed_at)
            facts.extend([
                _fact(task, "tasks_completed", employee, AttributionRole.EXECUTOR, task.completed_at),
                _fact(task, "task_cycle_seconds_avg", employee, AttributionRole.EXECUTOR, task.completed_at, cycle_seconds),
                _fact(task, "task_cycle_seconds_p50", employee, AttributionRole.EXECUTOR, task.completed_at, cycle_seconds),
                _fact(task, "task_cycle_seconds_p90", employee, AttributionRole.EXECUTOR, task.completed_at, cycle_seconds),
            ])
            responsibility_started = _assignment_started_at(task.assignment_history, employee, task.completed_at, task.created_at)
            if not due_at_completion or responsibility_started <= due_at_completion:
                facts.append(_fact(task, "task_deadline_compliance", employee, AttributionRole.RESPONSIBLE, task.completed_at, int(not due_at_completion or task.completed_at <= due_at_completion)))
            rejected = task.review_history.filter(action=TaskReviewHistory.Action.REJECTED, created_at__lte=task.completed_at).exists()
            facts.append(_fact(task, "task_rejection_rate", employee, AttributionRole.EXECUTOR, task.completed_at, int(rejected), suffix="final"))
            facts.append(_fact(task, "review_acceptance_rate", employee, AttributionRole.EXECUTOR, task.completed_at, int(not rejected), suffix="final"))
        for index, wait in enumerate(task.waiting_periods.all()):
            end = min(wait.ended_at or period_to, period_to); start = max(wait.started_at, period_from)
            if start < end:
                employee = _employee_at(task.assignment_history, task.responsible_employee, start, "responsible")
                facts.append(_fact(task, "waiting_seconds", employee, AttributionRole.RESPONSIBLE, start, _seconds(start, end), suffix=str(wait.pk)))
        for change in task.deadline_history.all():
            if period_from <= change.created_at < period_to:
                employee = _employee_at(task.assignment_history, task.responsible_employee, change.created_at, "responsible")
                facts.append(_fact(task, "deadline_changes", employee, AttributionRole.RESPONSIBLE, change.created_at, suffix=str(change.pk)))
        for change in task.assignment_history.all():
            if period_from <= change.created_at < period_to and change.old_employee:
                facts.append(_fact(task, "reassignments", change.old_employee, AttributionRole.RESPONSIBLE, change.created_at, suffix=str(change.pk)))
        reopens = task.status_history.filter(from_status=TaskStatus.COMPLETED, created_at__gte=period_from, created_at__lt=period_to)
        for reopen in reopens:
            employee = _employee_at(task.assignment_history, task.responsible_employee, reopen.created_at, "responsible")
            facts.append(_fact(task, "task_reopen_rate", employee, AttributionRole.RESPONSIBLE, reopen.created_at, 1, suffix=str(reopen.pk)))

    request_qs = ServiceRequest.objects.filter(
        Q(created_at__gte=period_from, created_at__lt=period_to)
        | Q(resolved_at__gte=period_from, resolved_at__lt=period_to)
        | (Q(waiting_periods__started_at__lt=period_to) & (Q(waiting_periods__ended_at__gt=period_from) | Q(waiting_periods__ended_at__isnull=True)))
    ).select_related("requester", "assigned_employee", "responsible_employee").prefetch_related(
        "assignment_history", "waiting_periods", "status_history"
    ).distinct()
    for item in request_qs:
        if period_from <= item.created_at < period_to:
            facts.append(_fact(item, "requests_created", item.requester, AttributionRole.REQUESTER, item.created_at))
        if item.resolved_at and period_from <= item.resolved_at < period_to:
            employee = _employee_at(item.assignment_history, item.assigned_employee or item.responsible_employee, item.resolved_at)
            duration = max(0, _seconds(item.created_at, item.resolved_at) - _waiting_seconds(item.waiting_periods.all(), item.created_at, item.resolved_at))
            facts.extend([
                _fact(item, "requests_resolved", employee, AttributionRole.EXECUTOR, item.resolved_at),
                _fact(item, "request_resolution_seconds_avg", employee, AttributionRole.EXECUTOR, item.resolved_at, duration),
                _fact(item, "request_resolution_seconds_p50", employee, AttributionRole.EXECUTOR, item.resolved_at, duration),
                _fact(item, "request_resolution_seconds_p90", employee, AttributionRole.EXECUTOR, item.resolved_at, duration),
            ])
        for wait in item.waiting_periods.all():
            end = min(wait.ended_at or period_to, period_to); start = max(wait.started_at, period_from)
            if start < end:
                employee = _employee_at(item.assignment_history, item.assigned_employee or item.responsible_employee, start)
                code = "waiting_requester_seconds" if wait.waiting_type == RequestStatus.WAITING_REQUESTER else "waiting_external_seconds"
                facts.append(_fact(item, code, employee, AttributionRole.EXECUTOR, start, _seconds(start, end), suffix=str(wait.pk)))
        for history in item.status_history.filter(from_status__in=(RequestStatus.RESOLVED, RequestStatus.CLOSED), created_at__gte=period_from, created_at__lt=period_to):
            employee = _employee_at(item.assignment_history, item.assigned_employee or item.responsible_employee, history.created_at)
            facts.append(_fact(item, "request_reopen_rate", employee, AttributionRole.EXECUTOR, history.created_at, 1, suffix=str(history.pk)))

    sla_qs = SLAMetricInstance.objects.filter(
        Q(achieved_at__gte=period_from, achieved_at__lt=period_to) | Q(breached_at__gte=period_from, breached_at__lt=period_to)
    ).select_related("sla_instance__request__assigned_employee", "sla_instance__request__responsible_employee")
    for metric in sla_qs:
        at = metric.achieved_at or metric.breached_at
        request = metric.sla_instance.request
        employee = _employee_at(request.assignment_history, request.assigned_employee or request.responsible_employee, at)
        code = "sla_response_compliance" if metric.metric_type == MetricType.RESPONSE else "sla_resolution_compliance"
        facts.append(_fact(request, code, employee, AttributionRole.EXECUTOR, at, int(metric.status == SLAMetricStatus.ACHIEVED), suffix=str(metric.pk)))
        if metric.status == SLAMetricStatus.BREACHED:
            facts.append(_fact(request, "sla_breaches", employee, AttributionRole.EXECUTOR, at, suffix=str(metric.pk)))
    facts = [fact for fact in facts if fact]
    with transaction.atomic():
        PerformanceFact.objects.filter(calculation_version=CALCULATION_VERSION, occurred_at__gte=period_from, occurred_at__lt=period_to).delete()
        PerformanceFact.objects.bulk_create(facts, ignore_conflicts=True, batch_size=1000)
    return len(facts)


def _percentile(values, percentile):
    if not values: return None
    values = sorted(values); position = (len(values) - 1) * percentile
    lower = int(position); upper = min(lower + 1, len(values) - 1); fraction = Decimal(str(position - lower))
    return values[lower] + (values[upper] - values[lower]) * fraction


def _metric_value(code, facts):
    values = [fact.value for fact in facts]
    if not values: return None
    if code.endswith("_p50"): return Decimal(str(median(values)))
    if code.endswith("_p90"): return _percentile(values, .9)
    if code.endswith("_avg"): return sum(values) / len(values)
    if code.endswith("_rate") or code.endswith("_compliance"): return sum(values) * 100 / len(values)
    return sum(values)


def aggregate_employee(employee, period_from, period_to, reporting_timezone):
    qs = PerformanceFact.objects.filter(employee=employee, occurred_at__gte=period_from, occurred_at__lt=period_to, calculation_version=CALCULATION_VERSION)
    rows = []
    with transaction.atomic():
        for code in METRICS:
            selected = list(qs.filter(metric_code=code))
            value = _metric_value(code, selected)
            if code == "active_tasks": value = Task.objects.filter(Q(responsible_employee=employee) | Q(executor_employee=employee), status__in=ACTIVE_TASKS).distinct().count()
            elif code == "overdue_tasks": value = Task.objects.filter(Q(responsible_employee=employee) | Q(executor_employee=employee), status__in=ACTIVE_TASKS, due_at__lt=timezone.now()).distinct().count()
            elif code in ("active_requests", "backlog_requests"): value = ServiceRequest.objects.filter(Q(assigned_employee=employee) | Q(responsible_employee=employee)).exclude(status__in=TERMINAL_REQUESTS).distinct().count()
            elif code == "throughput": value = _metric_value("tasks_completed", list(qs.filter(metric_code="tasks_completed"))) or 0
            elif code == "net_flow": value = (sum(f.value for f in qs.filter(metric_code="tasks_created")) - sum(f.value for f in qs.filter(metric_code="tasks_completed")))
            defaults = {"value": value, "sample_size": len(selected), "status": "measured" if value is not None else "no_data", "explanation": {"population": METRICS[code].population, "interval": "[from,to)", "source_facts": len(selected)}}
            row, _ = PerformanceAggregate.objects.update_or_create(subject_type=SubjectType.EMPLOYEE, subject_id=employee.pk, period_from=period_from, period_to=period_to, reporting_timezone=reporting_timezone, metric_code=code, calculation_version=CALCULATION_VERSION, defaults=defaults)
            rows.append(row)
    return rows
