from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from audit.services import record
from employees.models import Employee

from .integrations import provision_course_assignment
from .models import Certificate, Course, CourseAssignment


def _employees_for_rule(rule):
    qs = Employee.objects.filter(status=Employee.Status.ACTIVE, user__isnull=False)
    if rule.employee_id:
        qs = qs.filter(pk=rule.employee_id)
    if rule.role_id:
        qs = qs.filter(user__role_assignments__role_id=rule.role_id)
    if rule.department_id:
        qs = qs.filter(department_id=rule.department_id)
    if rule.facility_id:
        qs = qs.filter(facilities__id=rule.facility_id)
    if rule.position:
        qs = qs.filter(position__iexact=rule.position)
    if rule.region_id:
        qs = qs.filter(facilities__cluster__region_id=rule.region_id)
    return qs.distinct()


def _source_for_rule(rule):
    if rule.role_id:
        return CourseAssignment.Source.ROLE_RULE
    if rule.position:
        return CourseAssignment.Source.POSITION_RULE
    if rule.department_id:
        return CourseAssignment.Source.DEPARTMENT_RULE
    return CourseAssignment.Source.SCHEDULE


@transaction.atomic
def assign_courses_by_audience(now=None):
    now = now or timezone.now()
    created_count = 0
    courses = Course.objects.filter(status=Course.Status.PUBLISHED).prefetch_related("audience_rules")
    for course in courses:
        for rule in course.audience_rules.all():
            for employee in _employees_for_rule(rule):
                if CourseAssignment.objects.filter(course=course, employee=employee).exclude(
                    status__in=[CourseAssignment.Status.CANCELLED, CourseAssignment.Status.EXPIRED]
                ).exists():
                    continue
                assignment = CourseAssignment.objects.create(
                    course=course,
                    employee=employee,
                    assigned_by=course.author,
                    due_at=now + timedelta(days=30),
                    is_mandatory=rule.is_required,
                    source=_source_for_rule(rule),
                )
                provision_course_assignment(assignment, create_task=rule.is_required)
                record(course.author, "learning.course_assigned_by_rule", assignment, new_values={"rule_id": rule.id})
                created_count += 1
    return created_count


@transaction.atomic
def reassign_expired_certificates(now=None):
    now = now or timezone.now()
    created_count = 0
    certificates = Certificate.objects.filter(
        expires_at__lt=now,
        course__status=Course.Status.PUBLISHED,
        course__repeat_after_days__isnull=False,
    ).exclude(status=Certificate.Status.REVOKED).select_related("course", "employee", "course__author")
    for certificate in certificates:
        exists = CourseAssignment.objects.filter(
            course=certificate.course,
            employee=certificate.employee,
            assigned_at__gt=certificate.issued_at,
        ).exclude(status__in=[CourseAssignment.Status.CANCELLED, CourseAssignment.Status.EXPIRED]).exists()
        if exists:
            continue
        due_at = now + timedelta(days=certificate.course.repeat_after_days or 30)
        assignment = CourseAssignment.objects.create(
            course=certificate.course,
            employee=certificate.employee,
            assigned_by=certificate.course.author,
            due_at=due_at,
            is_mandatory=True,
            source=CourseAssignment.Source.CERTIFICATE_EXPIRATION,
            comment="Повторная аттестация после истечения сертификата",
        )
        provision_course_assignment(assignment, create_task=True)
        record(certificate.course.author, "learning.course_reassigned", assignment, new_values={"certificate_id": certificate.id})
        created_count += 1
    return created_count
