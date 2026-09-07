from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from audit.services import AuditService
from events.services import DomainEventService
from .models import (
    Employee,
    EmployeeAssignment,
    EmployeeManagerAssignment,
    EmployeeNumberSequence,
    FunctionalGroup,
    FunctionalGroupMembership,
    Team,
    TeamMembership,
)


class EmployeeNumberService:
    @staticmethod
    @transaction.atomic
    def allocate() -> str:
        try:
            sequence = EmployeeNumberSequence.objects.select_for_update().get(key="employee")
        except EmployeeNumberSequence.DoesNotExist:
            try:
                EmployeeNumberSequence.objects.create(key="employee", next_value=1)
            except IntegrityError:
                pass
            sequence = EmployeeNumberSequence.objects.select_for_update().get(key="employee")
        value = sequence.next_value
        sequence.next_value = value + 1
        sequence.save(update_fields=["next_value"])
        return f"EMP-{value:06d}"


class EmployeeService:
    @staticmethod
    @transaction.atomic
    def create(*, actor_user=None, **data) -> Employee:
        employee = Employee.objects.create(**data)
        AuditService.record(actor_user=actor_user, action="employee.created", entity=employee, new_value={"display_name": employee.display_name})
        DomainEventService.publish(event_type="employee.created", entity=employee, actor=actor_user, payload={"display_name": employee.display_name})
        DomainEventService.publish(event_type="people.employee.created", entity=employee, actor=actor_user, payload={"employee_number": employee.employee_number, "display_name": employee.display_name})
        return employee

    @staticmethod
    @transaction.atomic
    def deactivate(*, employee: Employee, actor_user=None) -> Employee:
        locked = Employee.objects.select_for_update().get(pk=employee.pk)
        old = {"is_active": locked.is_active, "status": locked.status}
        locked.is_active = False
        locked.status = Employee.Status.DISMISSED
        locked.dismissed_at = locked.dismissed_at or timezone.localdate()
        locked.updated_at = timezone.now()
        locked.save(update_fields=["is_active", "status", "dismissed_at", "updated_at"])
        AuditService.record(actor_user=actor_user, action="employee.deactivated", entity=locked, old_value=old, new_value={"is_active": False, "status": locked.status})
        DomainEventService.publish(event_type="employee.deactivated", entity=locked, actor=actor_user, payload={})
        return locked

    @staticmethod
    @transaction.atomic
    def update_profile(*, employee: Employee, actor_user=None, **changes) -> Employee:
        locked = Employee.objects.select_for_update().get(pk=employee.pk)
        allowed = {"first_name", "last_name", "middle_name", "work_email", "work_phone", "avatar", "hire_date"}
        invalid = set(changes) - allowed
        if invalid:
            raise ValidationError(f"Unsupported employee fields: {', '.join(sorted(invalid))}")
        old = {field: getattr(locked, field) for field in changes}
        for field, value in changes.items():
            setattr(locked, field, value)
        locked.save(update_fields=[*changes, "updated_at"])
        AuditService.record(actor_user=actor_user, action="people.employee.updated", entity=locked, old_value=old, new_value=changes)
        DomainEventService.publish(event_type="people.employee.updated", entity=locked, actor=actor_user, payload=changes)
        return locked

    @staticmethod
    @transaction.atomic
    def terminate(*, employee: Employee, actor_user=None, termination_date=None) -> Employee:
        locked = Employee.objects.select_for_update().get(pk=employee.pk)
        if locked.status == Employee.Status.TERMINATED:
            return locked
        now = timezone.now()
        old = {"status": locked.status, "is_active": locked.is_active, "dismissed_at": locked.dismissed_at}
        EmployeeAssignment.objects.select_for_update().filter(employee=locked, status=EmployeeAssignment.Status.ACTIVE).update(status=EmployeeAssignment.Status.ENDED, valid_to=now)
        EmployeeManagerAssignment.objects.select_for_update().filter(
            Q(employee=locked) | Q(manager=locked), status=EmployeeManagerAssignment.Status.ACTIVE
        ).update(status=EmployeeManagerAssignment.Status.ENDED, valid_to=now)
        FunctionalGroupMembership.objects.select_for_update().filter(employee=locked, is_active=True).update(is_active=False, active_until=now)
        for membership in TeamMembership.objects.select_for_update().filter(employee=locked, valid_to__isnull=True):
            membership.valid_to=max(now,membership.valid_from); membership.end_reason="employee_terminated"; membership.ended_by=actor_user; membership.version+=1
            membership.save(update_fields=["valid_to","end_reason","ended_by","version","updated_at"])
            AuditService.record(actor_user=actor_user,action="people.team.member_ended",entity=membership,new_value={"valid_to":membership.valid_to,"reason":"employee_terminated"})
            DomainEventService.publish(event_type="people.team.member_ended",entity=membership,actor=actor_user,payload={"employee_id":str(locked.pk),"reason":"employee_terminated"})
        for team in Team.objects.select_for_update().filter(Q(owner_employee=locked) | Q(lead_employee=locked)):
            before={"owner_employee":str(team.owner_employee_id) if team.owner_employee_id else None,"lead_employee":str(team.lead_employee_id) if team.lead_employee_id else None}
            if team.owner_employee_id==locked.pk: team.owner_employee=None
            if team.lead_employee_id==locked.pk: team.lead_employee=None
            team.version+=1; team.save(update_fields=["owner_employee","lead_employee","version","updated_at"])
            AuditService.record(actor_user=actor_user,action="people.team.leadership_vacated",entity=team,old_value=before,new_value={"owner_employee":str(team.owner_employee_id) if team.owner_employee_id else None,"lead_employee":str(team.lead_employee_id) if team.lead_employee_id else None})
            DomainEventService.publish(event_type="people.team.leadership_vacated",entity=team,actor=actor_user,payload={"employee_id":str(locked.pk)})
        locked.invitations.select_for_update().filter(used_at__isnull=True, revoked_at__isnull=True).update(revoked_at=now, status="revoked", revoke_reason="employee_terminated")
        from .models import OnboardingInstance
        active_onboarding = OnboardingInstance.objects.select_for_update().filter(employee=locked, status__in=["pending", "active", "paused"])
        for onboarding in active_onboarding:
            onboarding.status = "cancelled"; onboarding.cancelled_at = now; onboarding.cancellation_reason = "employee_terminated"; onboarding.version += 1
            onboarding.save(update_fields=["status", "cancelled_at", "cancellation_reason", "version", "updated_at"])
            onboarding.steps.exclude(status__in=["completed", "skipped"]).update(status="cancelled")
        if locked.user_id:
            locked.user.is_active = False
            locked.user.save(update_fields=["is_active"])
            from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
            for token in OutstandingToken.objects.filter(user_id=locked.user_id):
                BlacklistedToken.objects.get_or_create(token=token)
        locked.status = Employee.Status.TERMINATED
        locked.account_access_state = Employee.AccountAccessState.REACTIVATION_REQUIRED
        locked.is_active = False
        locked.dismissed_at = termination_date or timezone.localdate()
        locked.manager = None
        locked.save(update_fields=["status", "account_access_state", "is_active", "dismissed_at", "manager", "updated_at"])
        new = {"status": locked.status, "is_active": False, "dismissed_at": locked.dismissed_at}
        AuditService.record(actor_user=actor_user, action="people.employee.terminated", entity=locked, old_value=old, new_value=new)
        DomainEventService.publish(event_type="people.employee.terminated", entity=locked, actor=actor_user, payload=new)
        return locked

    @staticmethod
    @transaction.atomic
    def reactivate(*, employee: Employee, actor_user=None) -> Employee:
        locked = Employee.objects.select_for_update().get(pk=employee.pk)
        old = {"status": locked.status, "is_active": locked.is_active}
        locked.status = Employee.Status.ACTIVE
        locked.account_access_state = Employee.AccountAccessState.REACTIVATION_REQUIRED
        locked.is_active = True
        locked.dismissed_at = None
        locked.save(update_fields=["status", "account_access_state", "is_active", "dismissed_at", "updated_at"])
        if locked.user_id:
            locked.user.is_active = False
            locked.user.save(update_fields=["is_active"])
        new = {"status": locked.status, "is_active": True}
        AuditService.record(actor_user=actor_user, action="people.employee.reactivated", entity=locked, old_value=old, new_value=new)
        DomainEventService.publish(event_type="people.employee.reactivated", entity=locked, actor=actor_user, payload=new)
        return locked


class AccountAccessService:
    @staticmethod
    @transaction.atomic
    def set_access(*, employee, actor_user, enabled, action):
        locked = Employee.objects.select_for_update().select_related("user").get(pk=employee.pk)
        if not locked.user_id:
            raise ValidationError("Employee has no account.")
        if enabled and (not locked.is_active or locked.status == Employee.Status.TERMINATED):
            raise ValidationError("Terminated employee access cannot be restored.")
        locked.user.is_active = enabled
        locked.user.save(update_fields=["is_active"])
        locked.account_access_state = Employee.AccountAccessState.NORMAL if enabled else (Employee.AccountAccessState.SUSPENDED if action == "suspended" else Employee.AccountAccessState.BLOCKED)
        locked.save(update_fields=["account_access_state", "updated_at"])
        payload = {"employee_id": str(locked.pk), "enabled": enabled}
        AuditService.record(actor_user=actor_user, action=f"people.account.{action}", entity=locked, new_value=payload)
        DomainEventService.publish(event_type=f"people.account.{action}", entity=locked, actor=actor_user, payload=payload)
        return locked


class EmployeeAssignmentService:
    @staticmethod
    @transaction.atomic
    def start(*, employee: Employee, actor_user=None, is_primary=False, valid_from=None, **context) -> EmployeeAssignment:
        locked = Employee.objects.select_for_update().get(pk=employee.pk)
        if not locked.is_active or locked.status == Employee.Status.TERMINATED:
            raise ValidationError("Terminated employee cannot receive assignments.")
        org_unit=context.get("org_unit")
        if org_unit and (not org_unit.is_active or getattr(org_unit,"status","active")!="active"):
            raise ValidationError("Closed organizational unit cannot receive active assignments.")
        if is_primary and EmployeeAssignment.objects.select_for_update().filter(employee=locked, is_primary=True, status=EmployeeAssignment.Status.ACTIVE).exists():
            raise ValidationError("Employee already has an active primary assignment.")
        assignment = EmployeeAssignment.objects.create(employee=locked, is_primary=is_primary, valid_from=valid_from or timezone.now(), **context)
        if is_primary:
            locked.position_ref = assignment.position
            locked.org_unit = assignment.org_unit
            locked.legal_entity = assignment.legal_entity
            locked.primary_location = assignment.location
            locked.save(update_fields=["position_ref", "org_unit", "legal_entity", "primary_location", "updated_at"])
        payload = {"employee_id": str(locked.pk), "is_primary": is_primary}
        AuditService.record(actor_user=actor_user, action="people.assignment.started", entity=assignment, new_value=payload)
        DomainEventService.publish(event_type="people.assignment.started", entity=assignment, actor=actor_user, payload=payload)
        return assignment

    @staticmethod
    @transaction.atomic
    def end(*, assignment: EmployeeAssignment, actor_user=None, valid_to=None) -> EmployeeAssignment:
        locked = EmployeeAssignment.objects.select_for_update().get(pk=assignment.pk)
        if locked.status != EmployeeAssignment.Status.ACTIVE:
            return locked
        locked.status = EmployeeAssignment.Status.ENDED
        locked.valid_to = valid_to or timezone.now()
        locked.save(update_fields=["status", "valid_to", "updated_at"])
        payload = {"employee_id": str(locked.employee_id), "valid_to": locked.valid_to}
        AuditService.record(actor_user=actor_user, action="people.assignment.ended", entity=locked, old_value={"status": "active"}, new_value={"status": "ended", **payload})
        DomainEventService.publish(event_type="people.assignment.ended", entity=locked, actor=actor_user, payload=payload)
        return locked

    @classmethod
    @transaction.atomic
    def replace_primary(cls, *, employee: Employee, actor_user=None, valid_from=None, **context) -> EmployeeAssignment:
        locked = Employee.objects.select_for_update().get(pk=employee.pk)
        now = valid_from or timezone.now()
        current = EmployeeAssignment.objects.select_for_update().filter(employee=locked, is_primary=True, status=EmployeeAssignment.Status.ACTIVE).first()
        if current:
            cls.end(assignment=current, actor_user=actor_user, valid_to=now)
        return cls.start(employee=locked, actor_user=actor_user, is_primary=True, valid_from=now, **context)


class EmployeeManagerService:
    @staticmethod
    def _would_cycle(employee, manager):
        current = manager
        visited = {employee.pk}
        while current:
            if current.pk in visited:
                return True
            visited.add(current.pk)
            relation = EmployeeManagerAssignment.objects.filter(employee=current, status=EmployeeManagerAssignment.Status.ACTIVE).select_related("manager").first()
            current = relation.manager if relation else None
        return False

    @staticmethod
    def management_chain(employee: Employee):
        chain = []
        current = employee
        visited = {employee.pk}
        while True:
            relation = EmployeeManagerAssignment.objects.filter(employee=current, status=EmployeeManagerAssignment.Status.ACTIVE).select_related("manager").first()
            if relation is None or relation.manager_id in visited:
                break
            chain.append(relation.manager)
            visited.add(relation.manager_id)
            current = relation.manager
        return chain

    @staticmethod
    def direct_reports(manager: Employee):
        return Employee.objects.filter(
            manager_assignments__manager=manager,
            manager_assignments__status=EmployeeManagerAssignment.Status.ACTIVE,
        ).distinct()

    @classmethod
    @transaction.atomic
    def change(cls, *, employee: Employee, manager: Employee | None, actor_user=None, valid_from=None):
        locked = Employee.objects.select_for_update().get(pk=employee.pk)
        if manager is not None:
            manager = Employee.objects.select_for_update().get(pk=manager.pk)
            if manager.pk == locked.pk or cls._would_cycle(locked, manager):
                raise ValidationError("Manager hierarchy cycle is not allowed.")
        now = valid_from or timezone.now()
        previous = EmployeeManagerAssignment.objects.select_for_update().filter(employee=locked, status=EmployeeManagerAssignment.Status.ACTIVE).first()
        old_manager_id = previous.manager_id if previous else None
        if previous:
            previous.status = EmployeeManagerAssignment.Status.ENDED
            previous.valid_to = now
            previous.save(update_fields=["status", "valid_to"])
        relation = None
        if manager is not None:
            relation = EmployeeManagerAssignment.objects.create(employee=locked, manager=manager, valid_from=now)
        locked.manager = manager
        locked.save(update_fields=["manager", "updated_at"])
        payload = {"employee_id": str(locked.pk), "manager_id": str(manager.pk) if manager else None}
        AuditService.record(actor_user=actor_user, action="people.manager.changed", entity=locked, old_value={"manager_id": str(old_manager_id) if old_manager_id else None}, new_value=payload)
        DomainEventService.publish(event_type="people.manager.changed", entity=locked, actor=actor_user, payload=payload)
        return relation


class FunctionalGroupService:
    @staticmethod
    @transaction.atomic
    def add_member(*, group: FunctionalGroup, employee: Employee, actor_user=None, **data) -> FunctionalGroupMembership:
        membership = FunctionalGroupMembership.objects.select_for_update().filter(group=group, employee=employee, is_active=True).first()
        if membership is None:
            membership = FunctionalGroupMembership.objects.create(group=group, employee=employee, is_active=True, **data)
        else:
            for field, value in data.items():
                setattr(membership, field, value)
            if data:
                membership.save(update_fields=list(data))
        AuditService.record(actor_user=actor_user, action="functional_group.member_added", entity=group, new_value={"employee_id": str(employee.pk)})
        DomainEventService.publish(event_type="functional_group.member_added", entity=group, actor=actor_user, payload={"employee_id": str(employee.pk)})
        return membership

    @staticmethod
    @transaction.atomic
    def remove_member(*, group: FunctionalGroup, employee: Employee, actor_user=None) -> None:
        membership = FunctionalGroupMembership.objects.select_for_update().get(group=group, employee=employee, is_active=True)
        membership.is_active = False
        membership.active_until = membership.active_until or timezone.now()
        membership.save(update_fields=["is_active", "active_until"])
        AuditService.record(actor_user=actor_user, action="functional_group.member_removed", entity=group, old_value={"employee_id": str(employee.pk)})
        DomainEventService.publish(event_type="functional_group.member_removed", entity=group, actor=actor_user, payload={"employee_id": str(employee.pk)})
