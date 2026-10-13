"""Explicit synthetic department setup for older domain regression fixtures."""
from employees.models import Position
from organizations.models import OrgUnit
from .models import TaskTemplate


def department_for(employee):
    unit = employee.org_unit or OrgUnit.objects.create(name='Synthetic patch department')
    position = Position.objects.create(name='Synthetic patch head', org_unit=unit)
    unit.manager_position = position; unit.save(update_fields=['manager_position'])
    employee.org_unit = unit; employee.position_ref = position
    employee.save(update_fields=['org_unit', 'position_ref'])
    return unit


def configured_template(**data):
    data['responsible_department'] = department_for(data['responsible_target'].employee)
    return TaskTemplate.objects.create(**data)
