"""Department routing never grants permissions or infers an object scope."""
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from employees.assignment_targets import assignable_employees, assignment_visibility
from employees.models import AssignmentTarget
from organizations.object_policies import LocationAccessPolicy
from .exceptions import TaskValidationError


def department_head(department):
    now = timezone.now()
    if not department.is_active or department.status != 'active' or department.valid_from > now or (department.valid_to and department.valid_to <= now):
        raise TaskValidationError('Подразделение недоступно.', code='task_department_invalid')
    heads = list(assignable_employees().filter(org_unit=department, position_ref_id=department.manager_position_id, position_ref__is_active=True, position_ref__org_unit=department)[:2]) if department.manager_position_id else []
    if len(heads) != 1:
        raise TaskValidationError('Настройте должность руководителя и одного активного руководителя подразделения.', code='task_department_head_missing')
    return heads[0]


def employee_target(employee):
    # Existing target IDs remain intact; serialize creation through the employee row.
    from employees.models import Employee
    Employee.objects.select_for_update().get(pk=employee.pk)
    target = AssignmentTarget.objects.filter(target_type='employee', employee=employee).order_by('created_at', 'pk').first()
    return target or AssignmentTarget.objects.create(target_type='employee', employee=employee)


def eligible_for_location(employee, location):
    return not location or bool(employee.user_id and LocationAccessPolicy.allows(employee.user, 'location.view', location))


def validate_member(employee, department, location):
    if not assignable_employees().filter(pk=employee.pk, org_unit=department).exists() or not eligible_for_location(employee, location):
        raise TaskValidationError('Сотрудник должен быть активным, состоять в подразделении и иметь доступ к объекту.', code='task_assignment_invalid')


def calculate_deadline(priority, created_at, explicit=None):
    hours = settings.WORK_TASK_PRIORITY_HOURS.get(priority)
    if hours is None:
        if explicit is None:
            raise TaskValidationError('Для блокирующей задачи укажите явный дедлайн.', code='task_blocking_deadline_required')
        return explicit
    return created_at + timedelta(hours=hours)


def project_for(task):
    from projects.models import ProjectTaskLink
    try:
        link = task.project_link
    except ProjectTaskLink.DoesNotExist:
        return None
    return link.project if link.is_active else None


def validate_project_deadline(project, due):
    if not project.planned_end_at:
        raise TaskValidationError('Укажите обязательный дедлайн проекта.', code='project_deadline_required')
    if due and due > project.planned_end_at:
        raise TaskValidationError('Срок задачи позже дедлайна проекта.', code='task_project_deadline_conflict')


def assignment_choices(user, department, location=None):
    visible, _, _ = assignment_visibility(user)
    return [employee for employee in visible.filter(org_unit=department).order_by('last_name', 'first_name', 'pk') if eligible_for_location(employee, location)]
