from django.db import models
from django.utils import timezone

from .models import AssignmentTarget, Employee


class AssignmentTargetUnresolved(Exception):
    code = "assignment_target_unresolved"


class AssignmentTargetAmbiguous(Exception):
    code = "assignment_target_ambiguous"


class AssignmentResolver:
    @staticmethod
    def resolve(target: AssignmentTarget) -> list[Employee]:
        now = timezone.now()
        if target.target_type == AssignmentTarget.Type.EMPLOYEE:
            return [target.employee] if target.employee and target.employee.is_active else AssignmentResolver._unresolved()
        if target.target_type == AssignmentTarget.Type.POSITION:
            employees = list(Employee.objects.filter(position_ref=target.position, is_active=True).order_by("pk")[:2])
            if not employees:
                return AssignmentResolver._unresolved()
            if len(employees) > 1 and not target.position.allows_multiple_occupants:
                raise AssignmentTargetAmbiguous("Должность занята несколькими активными сотрудниками.")
            return employees
        if target.target_type == AssignmentTarget.Type.ORG_UNIT:
            employees = list(Employee.objects.filter(org_unit=target.org_unit, is_active=True))
        else:
            employees = list(Employee.objects.filter(
                functional_group_memberships__group=target.functional_group,
                functional_group_memberships__is_active=True,
            ).filter(
                models.Q(functional_group_memberships__active_from__isnull=True) | models.Q(functional_group_memberships__active_from__lte=now),
                models.Q(functional_group_memberships__active_until__isnull=True) | models.Q(functional_group_memberships__active_until__gte=now),
            ).distinct())
        return employees or AssignmentResolver._unresolved()

    @staticmethod
    def _unresolved():
        raise AssignmentTargetUnresolved("Не удалось определить активного исполнителя.")
