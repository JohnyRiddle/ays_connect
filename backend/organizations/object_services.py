import hashlib
import json
from contextlib import contextmanager
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection, transaction
from django.db.models import F, Q
from django.utils import timezone
from rest_framework.exceptions import APIException, NotFound, PermissionDenied, ValidationError

from audit.services import AuditService
from events.services import DomainEventService
from employees.models import Employee, EmployeeAssignment
from .models import Location, LocationIdempotency, LocationResponsibility
from .object_policies import LocationAccessPolicy


class ObjectConflict(APIException):
    status_code = 409
    default_code = "location_conflict"
    default_detail = "Карточка изменена. Обновите данные и повторите действие."


@contextmanager
def object_write():
    # A savepoint restores the capability flag even if a caller catches an error.
    with transaction.atomic():
        previous = ""
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                # All object writes and binding checks serialize with archive/tree moves.
                cursor.execute("SELECT pg_advisory_xact_lock(719230440101)")
                cursor.execute("SELECT current_setting('ays.objects_write', true)")
                previous = cursor.fetchone()[0] or ""
                cursor.execute("SELECT set_config('ays.objects_write', 'on', true)")
        yield
        if connection.vendor == "postgresql" and not connection.needs_rollback:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('ays.objects_write', %s, true)", [previous])


def require_available_location(location, user=None):
    """Consumer hook inside an existing transaction; protects archive vs binding races."""
    if not location:
        return
    if not connection.in_atomic_block:
        raise RuntimeError("Location binding requires an atomic transaction")
    with object_write():
        current = Location.objects.get(pk=location.pk)
        if user and current.node_kind != "unclassified" and not LocationAccessPolicy.allows(user, "location.view", current):
            raise NotFound()
        seen = set()
        while current:
            if current.pk in seen or current.is_archived or not current.is_active:
                raise ValidationError("Локация недоступна для новых связей.")
            seen.add(current.pk)
            current = current.parent


class ObjectService:
    INPUT = {"name", "business_type", "timezone", "parent", "address", "legal_entity", "org_unit", "contacts", "work_schedule", "description", "manager", "technical", "confirm_duplicate"}
    EDIT = {"name", "business_type", "timezone", "address", "org_unit", "contacts", "work_schedule", "description"}

    @staticmethod
    def authorize(user, permission, location):
        if not LocationAccessPolicy.allows(user, "location.view", location) or not LocationAccessPolicy.allows(user, permission, location):
            raise PermissionDenied()

    @staticmethod
    def record(location, user, action, old=None, new=None):
        AuditService.record(actor_user=user, actor_employee=getattr(user, "employee", None), action=f"location.{action}", entity=location, old_value=old, new_value=new)
        DomainEventService.publish(event_type=f"location.{action}", entity=location, actor=user,
            payload={"location_id": str(location.pk), "version": location.version, **(new or {})})

    @staticmethod
    def validate(location):
        if not location.name.strip():
            raise ValidationError({"name": "Укажите название."})
        try:
            ZoneInfo(location.timezone)
        except (ZoneInfoNotFoundError, ValueError, TypeError):
            raise ValidationError({"timezone": "Укажите действующий часовой пояс IANA."})
        if location.node_kind == "object" and location.business_type not in Location.BusinessType.values:
            raise ValidationError({"business_type": "Выберите тип объекта."})
        if location.org_unit_id and (not location.org_unit.is_active or location.org_unit.status != "active" or location.org_unit.legal_entity_id != location.legal_entity_id):
            raise ValidationError({"org_unit": "Подразделение и юрлицо должны быть согласованы и действовать."})
        if location.legal_entity_id and not location.legal_entity.is_active:
            raise ValidationError({"legal_entity": "Юрлицо недоступно."})
        location.full_clean(exclude=["code"])

    @staticmethod
    def parent(location, parent):
        allowed = {"geography": {"geography", "site", "object"}, "site": {"object"}, "object": {"zone"}, "zone": {"zone"}}
        if parent is None:
            if location.node_kind == "zone":
                raise ValidationError({"parent": "Зоне нужен объект."})
            return
        parent = Location.objects.get(pk=parent.pk)
        if parent.is_archived or not parent.is_active or location.node_kind not in allowed.get(parent.node_kind, set()):
            raise ValidationError({"parent": "Недопустимый родитель."})
        current, seen, has_object = parent, {location.pk}, False
        while current:
            if current.is_archived or not current.is_active:
                raise ValidationError({"parent": "Родительская локация недоступна."})
            if current.pk in seen:
                raise ValidationError({"parent": "Циклическая иерархия запрещена."})
            seen.add(current.pk)
            has_object |= current.node_kind == "object"
            current = current.parent
        if location.node_kind == "zone" and not has_object:
            raise ValidationError({"parent": "Зона должна принадлежать объекту."})
        return parent

    @staticmethod
    def relation(user, value, model):
        if value is None:
            return
        if model is Location:
            visible = LocationAccessPolicy.visible(user)
        else:
            from access_control.services import PermissionService
            if model is Employee:
                from employees.onboarding_api import visible_employees
                visible = visible_employees(user, "people.directory.view")
            else:
                # Organization related entities must satisfy their own object-level permission.
                code = "organization.view"
                if not ObjectService.organization_visible(user, model).filter(pk=value.pk).exists():
                    raise NotFound()
                visible = model.objects.all()
        if not visible.filter(pk=value.pk).exists():
            raise NotFound()

    @staticmethod
    def organization_visible(user, model):
        if user.is_superuser:
            return model.objects.all()
        from access_control.models import EmployeeRole
        actor = getattr(user, "employee", None)
        if not actor or not actor.is_active:
            return model.objects.none()
        now = timezone.now()
        query = Q(pk__in=[])
        grants = EmployeeRole.objects.filter(employee=actor, is_active=True, role__is_active=True,
            role__permission_grants__permission__code="organization.view").filter(
                Q(active_from__isnull=True) | Q(active_from__lte=now),
                Q(active_until__isnull=True) | Q(active_until__gt=now)).distinct()
        from .models import LegalEntity
        for grant in grants:
            for scope in grant.role.permission_grants.filter(permission__code="organization.view").values_list("scope", flat=True):
                if scope == "global":
                    return model.objects.all()
                if scope == "legal_entity" and grant.legal_entity_id:
                    query |= Q(pk=grant.legal_entity_id) if model is LegalEntity else Q(legal_entity_id=grant.legal_entity_id)
                if scope == "org_unit" and grant.org_unit_id and model is not LegalEntity:
                    query |= Q(pk=grant.org_unit_id)
        return model.objects.filter(query)

    @staticmethod
    def lock_employees(values):
        ids = sorted({value.pk for value in values if value}, key=str)
        return {row.pk: row for row in Employee.objects.select_for_update().filter(pk__in=ids).order_by("pk")}

    @classmethod
    def assign(cls, location, role, employee, user):
        if employee and (not employee.is_active or employee.status in {"terminated", "dismissed", "archived", "suspended", "inactive"}):
            raise ValidationError({role: "Ответственный должен быть действующим сотрудником."})
        now = timezone.now()
        LocationResponsibility.objects.filter(location=location, role=role, valid_to__isnull=True).update(valid_to=now, is_active=False, end_reason="reassigned")
        if employee:
            LocationResponsibility.objects.create(location=location, employee=employee, role=role, valid_from=now)

    @classmethod
    @transaction.atomic
    def create(cls, *, user, key, data):
        if not key or len(key) > 128 or not key.strip():
            raise ValidationError({"Idempotency-Key": "Укажите ключ запроса (до 128 символов)."})
        if not set(data) <= cls.INPUT:
            raise ValidationError("Недопустимые поля создания.")
        payload = {k: str(v.pk) if hasattr(v, "pk") else v for k, v in data.items()}
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, cls=DjangoJSONEncoder, ensure_ascii=False).encode()).hexdigest()
        people = cls.lock_employees([data.get("manager"), data.get("technical")])
        with object_write():
            candidate = Location(node_kind="object", business_status="preparation", **{k: v for k, v in data.items() if k not in {"manager", "technical", "confirm_duplicate"}})
            if not LocationAccessPolicy.create_context(user, candidate) or not LocationAccessPolicy.create_context(user, candidate, "location.view"):
                raise PermissionDenied()
            for field in ("parent", "legal_entity", "org_unit", "manager", "technical"):
                value = data.get(field)
                if value:
                    cls.relation(user, value, value.__class__)
            existing = LocationIdempotency.objects.filter(actor=user, operation="create", key=key).first()
            if existing:
                if existing.payload_hash != digest:
                    raise ObjectConflict("Ключ уже использован для другого запроса.")
                if not LocationAccessPolicy.allows(user, "location.view", existing.location):
                    raise NotFound()
                return existing.location, False
            candidate.parent = cls.parent(candidate, candidate.parent)
            cls.validate(candidate)
            for role in ("manager", "technical"):
                value = data.get(role)
                if value:
                    employee = people[value.pk]
                    if not employee.is_active or employee.status in {"terminated", "dismissed", "archived", "suspended", "inactive"}:
                        raise ValidationError({role: "Ответственный должен быть действующим сотрудником."})
                    if not LocationAccessPolicy.create_context(user, candidate, "location.assign_responsible"):
                        raise PermissionDenied()
            import unicodedata
            normalize = lambda text: " ".join(unicodedata.normalize("NFKC", text).casefold().split())
            names = LocationAccessPolicy.visible(user).filter(node_kind="object", parent=candidate.parent, is_archived=False).values_list("name", flat=True)
            if not data.get("confirm_duplicate") and any(normalize(name) == normalize(candidate.name) for name in names):
                raise ValidationError({"confirm_duplicate": "Найден похожий доступный объект. Подтвердите создание."})
            if connection.vendor != "postgresql":
                raise ValidationError("Создание объектов требует PostgreSQL.")
            while True:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT nextval('organizations_object_code_seq')")
                    candidate.code = f"OBJ-{cursor.fetchone()[0]:06d}"
                if not Location.objects.filter(code=candidate.code).exists():
                    break
            candidate.name = candidate.name.strip()
            candidate.save()
            for role in ("manager", "technical"):
                employee = data.get(role)
                if employee:
                    cls.assign(candidate, role, people[employee.pk], user)
            cls.record(candidate, user, "created", new={"name": candidate.name, "business_status": "preparation"})
            LocationIdempotency.objects.create(actor=user, operation="create", key=key, payload_hash=digest, location=candidate)
            return candidate, True

    @classmethod
    def locked(cls, location, version):
        current = Location.objects.select_for_update().get(pk=location.pk)
        if current.version != version:
            raise ObjectConflict()
        return current

    @classmethod
    @transaction.atomic
    def edit(cls, *, location, user, version, data):
        with object_write():
            location = cls.locked(location, version)
            cls.authorize(user, "location.edit" if location.node_kind == "object" else "location.manage_zones", location)
            allowed = cls.EDIT if location.node_kind == "object" else {"name", "description"}
            if location.is_archived or not data or not set(data) <= allowed:
                raise ValidationError("Недопустимые поля или архивная карточка.")
            old = {key: str(getattr(location, key)) for key in data}
            for key, value in data.items():
                if key == "org_unit" and value:
                    cls.relation(user, value, value.__class__)
                setattr(location, key, value)
            cls.validate(location)
            location.version += 1
            location.save()
            cls.record(location, user, "edited", old, {key: str(getattr(location, key)) for key in data})
            return location

    @classmethod
    @transaction.atomic
    def responsibility(cls, *, location, user, version, role, employee):
        people = cls.lock_employees([employee])
        with object_write():
            location = cls.locked(location, version)
            cls.authorize(user, "location.assign_responsible", location)
            if location.node_kind != "object" or location.is_archived or role not in LocationResponsibility.Role.values:
                raise ValidationError("Назначение недоступно.")
            if employee:
                cls.relation(user, employee, Employee)
            cls.assign(location, role, people.get(employee.pk) if employee else None, user)
            location.version += 1
            location.save()
            cls.record(location, user, "responsibility_changed", new={"role": role})
            return location

    @classmethod
    @transaction.atomic
    def zone(cls, *, parent, user, version, name, description=""):
        with object_write():
            parent = cls.locked(parent, version)
            cls.authorize(user, "location.manage_zones", parent)
            zone = Location(name=name, description=description, parent=parent, node_kind="zone", timezone=parent.timezone, legal_entity=parent.legal_entity)
            cls.parent(zone, parent)
            cls.validate(zone)
            zone.save()
            parent.version += 1
            parent.save()
            cls.record(zone, user, "zone_created", new={"parent_id": str(parent.pk), "name": name})
            return zone

    @classmethod
    @transaction.atomic
    def lifecycle(cls, *, location, user, version, action, reason=""):
        with object_write():
            location = cls.locked(location, version)
            permission = {"archive": "archive", "restore": "restore"}.get(action, "change_status")
            cls.authorize(user, f"location.{permission}", location)
            old = {"business_status": location.business_status, "is_archived": location.is_archived}
            if action == "restore":
                if not location.is_archived:
                    raise ValidationError("Карточка не архивирована.")
                cls.parent(location, location.parent)
                location.is_archived = False
            elif action == "archive":
                if location.is_archived or (location.node_kind == "object" and location.business_status != "final_closed"):
                    raise ValidationError("Для архива объект должен быть окончательно закрыт.")
                ids = LocationAccessPolicy.descendants(location)
                from work_tasks.models import Task
                if Location.objects.filter(parent=location, is_archived=False, is_active=True).exists() or EmployeeAssignment.objects.filter(location_id__in=ids, status="active").exists() or LocationResponsibility.objects.filter(location_id__in=ids, valid_to__isnull=True).exists() or Task.objects.filter(location_id__in=ids).exclude(status__in=["completed", "cancelled"]).exists():
                    raise ValidationError("Архивирование заблокировано действующими связями. Обратитесь к уполномоченному сотруднику.")
                location.is_archived = True
            else:
                if location.node_kind != "object" or location.is_archived:
                    raise ValidationError("Изменение статуса недоступно.")
                transitions = {"operate": ({"preparation", "seasonal_closed"}, "operating"), "seasonal_close": ({"operating"}, "seasonal_closed"), "close": ({"preparation", "operating", "seasonal_closed"}, "final_closed"), "reopen": ({"final_closed"}, "preparation")}
                if action not in transitions or location.business_status not in transitions[action][0]:
                    raise ValidationError("Переход недоступен.")
                if action != "operate" or location.business_status == "seasonal_closed":
                    if not reason.strip():
                        raise ValidationError({"reason": "Укажите причину."})
                if action == "operate" and location.business_status == "preparation":
                    if not location.address.strip() or not location.legal_entity_id or not LocationResponsibility.objects.filter(location=location, role="manager", valid_to__isnull=True, employee__is_active=True).exists():
                        raise ValidationError("Для запуска нужны адрес/местоположение, юрлицо и действующий управляющий.")
                location.business_status = transitions[action][1]
            location.version += 1
            location.save()
            cls.record(location, user, action, old, {"business_status": location.business_status, "is_archived": location.is_archived, "reason": reason})
            return location

    @classmethod
    @transaction.atomic
    def move(cls, *, location, parent, user, version):
        with object_write():
            location = cls.locked(location, version)
            parent = Location.objects.get(pk=parent.pk) if parent else None
            cls.authorize(user, "location.move", location)
            if parent:
                cls.authorize(user, "location.move", parent)
            elif not LocationAccessPolicy.create_context(user, location, "location.move"):
                raise PermissionDenied()
            if location.is_archived:
                raise ValidationError("Архивная карточка не перемещается.")
            parent = cls.parent(location, parent)
            def root(node):
                while node and node.node_kind == "zone":
                    node = node.parent
                return node.pk if node else None
            if location.node_kind == "zone" and root(location) != root(parent):
                from django.apps import apps
                ids = LocationAccessPolicy.descendants(location)
                for model in apps.get_models():
                    for field in model._meta.concrete_fields:
                        if field.is_relation and field.remote_field.model is Location and model is not Location:
                            if model.objects.filter(**{f"{field.attname}__in": ids}).exists():
                                raise ValidationError("Межобъектное перемещение зоны со связями запрещено.")
                # Change context only on an unused subtree.
                Location.objects.filter(pk__in=ids).exclude(pk=location.pk).update(legal_entity=parent.legal_entity, version=F("version") + 1)
                location.legal_entity = parent.legal_entity
            old = {"parent_id": str(location.parent_id)}
            location.parent = parent
            location.version += 1
            location.save()
            cls.record(location, user, "moved", old, {"parent_id": str(parent.pk) if parent else None})
            return location

    @classmethod
    def end_employee_responsibilities(cls, employee, user):
        with object_write():
            now = timezone.now()
            for row in LocationResponsibility.objects.filter(employee=employee, valid_to__isnull=True).order_by("location_id"):
                row.valid_to = max(now, row.valid_from)
                row.is_active = False
                row.end_reason = "employee_terminated"
                row.save()
                location = Location.objects.select_for_update().get(pk=row.location_id)
                location.version += 1
                location.save()
                cls.record(location, user, "responsibility_ended", new={"role": row.role, "reason": "employee_terminated"})
