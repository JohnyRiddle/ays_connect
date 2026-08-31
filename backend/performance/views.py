from datetime import timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.db.models import Avg, Sum
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from employees.models import Employee

from .access import visible_employees
from .engine import aggregate_employee, build_facts
from .models import CALCULATION_VERSION, PerformanceAggregate, SubjectType
from .registry import METRICS, metric_payload


def _period(request):
    tz_name = request.query_params.get("timezone", "Asia/Novosibirsk")
    try: zone = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as exc: raise ValidationError({"timezone": "Unknown IANA timezone."}) from exc
    now = timezone.now().astimezone(zone)
    start = parse_datetime(request.query_params.get("from", "")) or now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = parse_datetime(request.query_params.get("to", "")) or now
    if timezone.is_naive(start): start = start.replace(tzinfo=zone)
    if timezone.is_naive(end): end = end.replace(tzinfo=zone)
    if start >= end: raise ValidationError({"period": "from must be before to"})
    return start, end, tz_name


def _serialize(rows):
    return {row.metric_code: {"value": float(row.value) if row.value is not None else None, "sample_size": row.sample_size, "status": row.status, "explanation": row.explanation} for row in rows}


def _employee_payload(employee, start, end, tz_name):
    rows = aggregate_employee(employee, start, end, tz_name)
    previous_start = start - (end - start)
    previous = aggregate_employee(employee, previous_start, start, tz_name)
    return {
        "employee": {"id": str(employee.pk), "name": employee.display_name, "position": employee.position, "org_unit_id": str(employee.org_unit_id) if employee.org_unit_id else None},
        "period": {"from": start, "to": end, "timezone": tz_name, "semantics": "[from,to)"},
        "calculation_version": CALCULATION_VERSION,
        "metrics": _serialize(rows), "previous_period": _serialize(previous),
    }


class MeView(APIView):
    def get(self, request):
        employee = getattr(request.user, "employee", None)
        if not employee: raise NotFound()
        return Response(_employee_payload(employee, *_period(request)))


class EmployeeSummaryView(APIView):
    def get(self, request, employee_id):
        employee = visible_employees(request.user).filter(pk=employee_id).first()
        if not employee: raise NotFound()
        return Response(_employee_payload(employee, *_period(request)))


class DimensionSummaryView(APIView):
    dimension = None

    def get(self, request, dimension_id):
        start, end, tz_name = _period(request)
        employees = visible_employees(request.user).filter(**{f"{self.dimension}_id": dimension_id})
        if not employees.exists(): raise NotFound()
        build_facts(start, end)
        items = [_employee_payload(employee, start, end, tz_name) for employee in employees]
        values = {}
        for code in METRICS:
            measured = [item["metrics"][code]["value"] for item in items if item["metrics"][code]["value"] is not None]
            values[code] = {"value": round(sum(measured) / len(measured), 2) if measured else None, "employees": len(measured), "status": "measured" if measured else "no_data"}
        return Response({"dimension": self.dimension, "id": str(dimension_id), "period": {"from": start, "to": end, "timezone": tz_name}, "metrics": values, "employees": items})


class OrgUnitSummaryView(DimensionSummaryView): dimension = "org_unit"
class LocationSummaryView(DimensionSummaryView): dimension = "primary_location"
class LegalEntitySummaryView(DimensionSummaryView): dimension = "legal_entity"


class OrgUnitEmployeesView(APIView):
    def get(self, request, dimension_id):
        start, end, tz_name = _period(request)
        employees = visible_employees(request.user).filter(org_unit_id=dimension_id)
        if not employees.exists(): raise NotFound()
        build_facts(start, end)
        return Response({"results": [_employee_payload(employee, start, end, tz_name) for employee in employees]})


class OverviewView(APIView):
    def get(self, request):
        start, end, tz_name = _period(request)
        employees = visible_employees(request.user)
        build_facts(start, end)
        items = [_employee_payload(employee, start, end, tz_name) for employee in employees]
        return Response({"period": {"from": start, "to": end, "timezone": tz_name}, "employee_count": len(items), "employees": items, "calculation_version": CALCULATION_VERSION})


class MetricDefinitionView(APIView):
    def get(self, request, code=None):
        payload = metric_payload(code)
        if code and payload is None: raise NotFound()
        return Response(payload)
