from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.utils import timezone

from audit.services import AuditService
from events.services import DomainEventService
from .models import Employee, Team, TeamMembership, TeamNumberSequence


class TeamConflict(ValidationError):
    pass


def _emit(*, actor, action, entity, before=None, after=None, reason=""):
    metadata = {"reason": reason} if reason else {}
    AuditService.record(actor_user=actor, action=action, entity=entity, old_value=before, new_value=after, metadata=metadata)
    DomainEventService.publish(event_type=action, entity=entity, actor=actor, payload={"before": before or {}, "after": after or {}, **metadata})


def _active_employee(employee):
    if not employee.is_active or employee.status in {Employee.Status.ARCHIVED, Employee.Status.SUSPENDED, Employee.Status.DISMISSED, Employee.Status.TERMINATED}:
        raise ValidationError("Недействующий сотрудник не может участвовать в команде.")


class TeamNumberService:
    @staticmethod
    @transaction.atomic
    def allocate():
        try:
            sequence = TeamNumberSequence.objects.select_for_update().get(key="team")
        except TeamNumberSequence.DoesNotExist:
            try: TeamNumberSequence.objects.create(key="team",next_value=1)
            except IntegrityError: pass
            sequence=TeamNumberSequence.objects.select_for_update().get(key="team")
        value = sequence.next_value
        sequence.next_value = F("next_value") + 1
        sequence.save(update_fields=["next_value"])
        return f"TEAM-{value:06d}"


class TeamService:
    UPDATE_FIELDS = {"name", "short_name", "description", "team_type", "legal_entity", "org_unit", "location", "metadata"}

    @staticmethod
    def _validate_parent(team, parent):
        if not parent:
            return
        cursor, seen = parent, set()
        while cursor:
            if cursor.pk in seen or (team and cursor.pk == team.pk):
                raise ValidationError("Нельзя создать циклическую иерархию команд.")
            seen.add(cursor.pk)
            cursor = cursor.parent_team
        if parent.valid_from > (team.valid_from if team else timezone.now()):
            raise ValidationError("Период дочерней команды должен находиться внутри периода родителя.")
        if team and parent.valid_to and (not team.valid_to or team.valid_to > parent.valid_to):
            raise ValidationError("Период дочерней команды должен находиться внутри периода родителя.")
        if team and team.legal_entity_id and parent.legal_entity_id and team.legal_entity_id != parent.legal_entity_id:
            raise ValidationError("Родительская и дочерняя команды должны относиться к одному юридическому лицу.")

    @classmethod
    def _validate_context(cls, team):
        cls._validate_parent(team, team.parent_team)
        if team.legal_entity_id and team.org_unit_id and team.org_unit.legal_entity_id and team.legal_entity_id != team.org_unit.legal_entity_id:
            raise ValidationError("Подразделение команды относится к другому юридическому лицу.")
        if team.legal_entity_id and team.location_id and team.location.legal_entity_id and team.legal_entity_id != team.location.legal_entity_id:
            raise ValidationError("Локация команды относится к другому юридическому лицу.")

    @classmethod
    @transaction.atomic
    def create(cls, *, actor_user=None, **data):
        candidate=Team(**data); cls._validate_context(candidate)
        if data.get("lead_employee"):
            raise ValidationError("Руководителя можно назначить только после добавления его в активную команду.")
        for employee in (data.get("owner_employee"), data.get("lead_employee")):
            if employee: _active_employee(employee)
        team = Team.objects.create(code=TeamNumberService.allocate(), created_by=actor_user, updated_by=actor_user, **data)
        _emit(actor=actor_user, action="people.team.created", entity=team, after={"code": team.code, "name": team.name})
        return team

    @classmethod
    @transaction.atomic
    def update(cls, *, team, expected_version, actor_user=None, **data):
        locked = Team.objects.select_for_update().get(pk=team.pk)
        if locked.version != expected_version: raise TeamConflict("Версия команды устарела.")
        forbidden = set(data) - cls.UPDATE_FIELDS
        if forbidden: raise ValidationError("Иерархию, руководство и lifecycle-поля можно изменять только отдельными операциями.")
        before = {key: getattr(locked, f"{key}_id", getattr(locked, key, None)) for key in data}
        for key, value in data.items(): setattr(locked, key, value)
        cls._validate_context(locked)
        locked.version += 1; locked.updated_by = actor_user
        locked.save(update_fields=[*data, "version", "updated_by", "updated_at"])
        safe_after={key:(str(value.pk) if hasattr(value,"pk") else value) for key,value in data.items()}
        _emit(actor=actor_user, action="people.team.updated", entity=locked, before={k:(str(v) if v is not None else None) for k,v in before.items()}, after=safe_after)
        return locked

    @staticmethod
    @transaction.atomic
    def transition(*, team, target, expected_version, actor_user=None, reason=""):
        locked = Team.objects.select_for_update().get(pk=team.pk)
        if locked.version != expected_version: raise TeamConflict("Версия команды устарела.")
        allowed={Team.Status.DRAFT:{Team.Status.ACTIVE,Team.Status.CLOSED},Team.Status.ACTIVE:{Team.Status.SUSPENDED,Team.Status.CLOSED},Team.Status.SUSPENDED:{Team.Status.ACTIVE,Team.Status.CLOSED},Team.Status.CLOSED:set()}
        if target not in allowed[locked.status]: raise ValidationError("Недопустимый переход статуса команды.")
        now = timezone.now()
        if target == Team.Status.ACTIVE and (locked.valid_from > now or (locked.valid_to and locked.valid_to <= now)):
            raise ValidationError("Нельзя активировать команду вне периода её действия.")
        old=locked.status; locked.status=target; locked.version+=1
        if target==Team.Status.CLOSED:
            locked.valid_to=max(now, locked.valid_from); locked.is_assignable=False
            for membership in TeamMembership.objects.select_for_update().filter(team=locked,valid_to__isnull=True):
                TeamMembershipService.end(membership=membership,actor_user=actor_user,reason="team_closed",at=locked.valid_to)
        locked.updated_by=actor_user; locked.save()
        event={Team.Status.ACTIVE:"resumed" if old==Team.Status.SUSPENDED else "activated",Team.Status.SUSPENDED:"suspended",Team.Status.CLOSED:"closed"}[target]
        _emit(actor=actor_user,action=f"people.team.{event}",entity=locked,before={"status":old},after={"status":target},reason=reason)
        return locked

    @classmethod
    @transaction.atomic
    def move(cls, *, team, parent, expected_version, actor_user=None):
        ids=list(Team.objects.select_for_update().values_list("pk",flat=True))
        locked=Team.objects.get(pk=team.pk)
        if locked.version!=expected_version: raise TeamConflict("Версия команды устарела.")
        cls._validate_parent(locked,parent); old=str(locked.parent_team_id) if locked.parent_team_id else None
        locked.parent_team=parent; locked.version+=1; locked.updated_by=actor_user; locked.save(update_fields=["parent_team","version","updated_by","updated_at"])
        _emit(actor=actor_user,action="people.team.moved",entity=locked,before={"parent_team":old},after={"parent_team":str(parent.pk) if parent else None})
        return locked

    @staticmethod
    @transaction.atomic
    def assign_leadership(*, team, employee, field, expected_version, actor_user=None):
        if field not in {"owner_employee","lead_employee"}: raise ValidationError("Unknown leadership field.")
        locked=Team.objects.select_for_update().get(pk=team.pk)
        if locked.version!=expected_version: raise TeamConflict("Версия команды устарела.")
        if locked.status == Team.Status.CLOSED and employee is not None:
            raise ValidationError("Закрытой команде нельзя назначать нового владельца или руководителя.")
        if employee:
            employee=Employee.objects.select_for_update().get(pk=employee.pk); _active_employee(employee)
            if field=="lead_employee" and not TeamMembership.objects.filter(team=locked,employee=employee,valid_to__isnull=True).exists():
                raise ValidationError("Руководитель должен быть активным участником команды.")
        old=getattr(locked,f"{field}_id"); setattr(locked,field,employee); locked.version+=1; locked.updated_by=actor_user
        locked.save(update_fields=[field,"version","updated_by","updated_at"])
        action="people.team.owner_changed" if field=="owner_employee" else "people.team.lead_changed"
        _emit(actor=actor_user,action=action,entity=locked,before={field:str(old) if old else None},after={field:str(employee.pk) if employee else None})
        return locked


class TeamMembershipService:
    @staticmethod
    def _overlaps(*, team, employee, start, end, exclude=None):
        queryset = TeamMembership.objects.select_for_update().filter(team=team, employee=employee)
        if exclude:
            queryset = queryset.exclude(pk=exclude.pk)
        if end is not None:
            queryset = queryset.filter(valid_from__lt=end)
        return queryset.filter(Q(valid_to__isnull=True) | Q(valid_to__gt=start)).exists()

    @staticmethod
    @transaction.atomic
    def add(*, team, employee, actor_user=None, **data):
        locked_team=Team.objects.select_for_update().get(pk=team.pk); locked_employee=Employee.objects.select_for_update().get(pk=employee.pk)
        _active_employee(locked_employee)
        if locked_team.status != Team.Status.ACTIVE: raise ValidationError("Новые участники допустимы только в активной команде.")
        start=data.get("valid_from") or timezone.now(); end=data.get("valid_to")
        if end is not None and end < start:
            raise ValidationError("Дата завершения членства не может быть раньше даты начала.")
        if start < locked_team.valid_from or (locked_team.valid_to and (not end or end > locked_team.valid_to)): raise ValidationError("Период членства находится вне периода команды.")
        existing=TeamMembership.objects.select_for_update().filter(team=locked_team,employee=locked_employee,valid_to__isnull=True).first()
        if existing:
            same=all(getattr(existing,key)==value for key,value in data.items())
            if same: return existing
            raise TeamConflict("У сотрудника уже есть активное членство в команде.")
        if TeamMembershipService._overlaps(team=locked_team, employee=locked_employee, start=start, end=end):
            raise TeamConflict("Период членства пересекается с существующей исторической записью.")
        data["valid_from"] = start
        membership=TeamMembership.objects.create(team=locked_team,employee=locked_employee,created_by=actor_user,**data)
        _emit(actor=actor_user,action="people.team.member_added",entity=membership,after={"team":str(team.pk),"employee":str(employee.pk),"role":membership.role})
        return membership

    @staticmethod
    @transaction.atomic
    def end(*, membership, actor_user=None, reason="", at=None):
        locked=TeamMembership.objects.select_for_update().get(pk=membership.pk)
        if locked.valid_to is not None: return locked
        locked.valid_to=max(at or timezone.now(), locked.valid_from); locked.ended_by=actor_user; locked.end_reason=reason; locked.version+=1; locked.save()
        _emit(actor=actor_user,action="people.team.member_ended",entity=locked,after={"valid_to":locked.valid_to},reason=reason)
        return locked

    @classmethod
    @transaction.atomic
    def change_role(cls, *, membership, role, actor_user=None, reason=""):
        old=TeamMembership.objects.select_for_update().select_related("team", "employee").get(pk=membership.pk)
        if old.valid_to is not None:
            raise TeamConflict("Роль завершённого членства изменить нельзя.")
        locked_team=Team.objects.select_for_update().get(pk=old.team_id)
        locked_employee=Employee.objects.select_for_update().get(pk=old.employee_id)
        _active_employee(locked_employee)
        if locked_team.status != Team.Status.ACTIVE:
            raise ValidationError("Роль можно менять только в активной команде.")
        if role not in TeamMembership.Role.values:
            raise ValidationError("Неизвестная роль участника команды.")
        if role == old.role:
            return old
        changed_at=max(timezone.now(), old.valid_from)
        old.valid_to=changed_at; old.ended_by=actor_user; old.end_reason=reason or "role_changed"; old.version+=1
        old.save(update_fields=["valid_to", "ended_by", "end_reason", "version", "updated_at"])
        new=TeamMembership.objects.create(team=old.team,employee=old.employee,role=role,membership_type=old.membership_type,allocation_percent=old.allocation_percent,is_primary_in_team=old.is_primary_in_team,valid_from=changed_at,created_by=actor_user)
        _emit(actor=actor_user,action="people.team.member_role_changed",entity=new,before={"role":old.role},after={"role":role},reason=reason)
        return new

    @staticmethod
    def as_of(team, at=None, include_descendants=False):
        at=at or timezone.now(); team_ids=[team.pk]
        if include_descendants:
            frontier=[team.pk]
            while frontier:
                frontier=list(Team.objects.filter(parent_team_id__in=frontier).values_list("pk",flat=True)); team_ids.extend(frontier)
        return TeamMembership.objects.filter(team_id__in=team_ids,valid_from__lte=at).filter(Q(valid_to__isnull=True)|Q(valid_to__gt=at)).select_related("employee","team").order_by("employee_id","team_id")
