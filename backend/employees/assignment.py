from django.db import models
from django.utils import timezone

from .models import AssignmentTarget, Employee, Team, TeamMembership


class AssignmentTargetUnresolved(Exception):
    code = "assignment_target_unresolved"


class AssignmentTargetAmbiguous(Exception):
    code = "assignment_target_ambiguous"


class AssignmentResolver:
    TEAM_STRATEGIES = {"team_lead", "team_owner", "all_active_members", "role_members", "explicit_member"}

    @staticmethod
    def resolve(target: AssignmentTarget, at=None) -> list[Employee]:
        now = at or timezone.now()
        if target.target_type == AssignmentTarget.Type.EMPLOYEE:
            return [target.employee] if target.employee and target.employee.is_active else AssignmentResolver._unresolved()
        if target.target_type == AssignmentTarget.Type.POSITION:
            employees = list(Employee.objects.filter(position_ref=target.position, is_active=True).order_by("pk")[:2])
            if not employees:
                return AssignmentResolver._unresolved()
            if len(employees) > 1 and not target.position.allows_multiple_occupants:
                raise AssignmentTargetAmbiguous("Должность занята несколькими активными сотрудниками.")
            return employees
        if target.target_type == AssignmentTarget.Type.TEAM:
            return AssignmentResolver.resolve_team(target, at=now)[0]
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
    def resolve_team(target, at=None):
        at=at or timezone.now(); team=target.team
        if not team or team.status != Team.Status.ACTIVE or not team.is_assignable or team.valid_from > at or (team.valid_to and team.valid_to <= at):
            return AssignmentResolver._unresolved()
        strategy=target.strategy or "all_active_members"
        if strategy not in AssignmentResolver.TEAM_STRATEGIES:
            raise AssignmentTargetUnresolved("Неизвестная стратегия разрешения команды.")
        if strategy == "role_members" and target.team_role not in TeamMembership.Role.values:
            raise AssignmentTargetUnresolved("Для ROLE_MEMBERS требуется допустимая роль.")
        if strategy == "explicit_member" and not target.explicit_employee_id:
            raise AssignmentTargetUnresolved("Для EXPLICIT_MEMBER требуется сотрудник.")
        qs=TeamMembership.objects.filter(team=team,valid_from__lte=at).filter(models.Q(valid_to__isnull=True)|models.Q(valid_to__gt=at)).select_related("employee")
        excluded=[]
        if strategy=="team_lead":
            qs=qs.filter(employee=team.lead_employee)
        elif strategy=="team_owner":
            owner=team.owner_employee
            if not owner:
                return AssignmentResolver._unresolved()
            if owner.is_active and owner.status not in {Employee.Status.TERMINATED,Employee.Status.DISMISSED,Employee.Status.ARCHIVED,Employee.Status.SUSPENDED}:
                return [owner], {"strategy": strategy, "excluded": []}
            return AssignmentResolver._unresolved()
        elif strategy=="role_members": qs=qs.filter(role=target.team_role)
        elif strategy=="explicit_member": qs=qs.filter(employee=target.explicit_employee)
        else:
            for membership in qs.filter(role=TeamMembership.Role.OBSERVER).order_by("employee_id"):
                excluded.append({"employee_id":str(membership.employee_id),"reason":"observer_excluded"})
            qs=qs.exclude(role=TeamMembership.Role.OBSERVER)
        included=[]
        for membership in qs.order_by("employee_id"):
            employee=membership.employee
            if employee.is_active and employee.status not in {Employee.Status.TERMINATED,Employee.Status.DISMISSED,Employee.Status.ARCHIVED,Employee.Status.SUSPENDED}: included.append(employee)
            else: excluded.append({"employee_id":str(employee.pk),"reason":"inactive_employee"})
        if not included: return AssignmentResolver._unresolved()
        return included,{"strategy":strategy,"excluded":excluded}

    @staticmethod
    def _unresolved():
        raise AssignmentTargetUnresolved("Не удалось определить активного исполнителя.")
