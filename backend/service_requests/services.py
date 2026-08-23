from decimal import Decimal, InvalidOperation
from uuid import UUID
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework.exceptions import ValidationError as DRFValidationError
from access_control.models import EmployeeRole
from access_control.services import PermissionService
from audit.services import AuditService
from events.services import DomainEventService
from employees.models import Employee
from organizations.models import LegalEntity, Location, OrgUnit
from .models import AccessScope, FieldType, RequestTypeSchemaVersion


class CatalogError(DRFValidationError):
    code = "service_catalog_invalid"


def require(actor, user, permission):
    if not (user and user.is_superuser) and not PermissionService.has_permission(employee=actor, permission=permission):
        raise PermissionDenied("Insufficient permissions.")


class CategoryService:
    @staticmethod
    def validate_parent(category, parent):
        if not parent: return
        if category and parent.pk == category.pk: raise CatalogError("Category cannot be its own parent.")
        cursor, seen = parent, set()
        while cursor:
            if cursor.pk in seen or (category and cursor.pk == category.pk): raise CatalogError("Category hierarchy cycle detected.")
            seen.add(cursor.pk); cursor = cursor.parent

    @classmethod
    @transaction.atomic
    def move(cls, category, parent, actor, user):
        require(actor, user, "service_catalog.manage"); category = type(category).objects.select_for_update().get(pk=category.pk)
        cls.validate_parent(category, parent); old = category.parent_id; category.parent = parent; category.save(update_fields=["parent", "updated_at"])
        AuditService.record(action="service_category.moved", entity=category, actor_user=user, actor_employee=actor, old_value={"parent": old}, new_value={"parent": parent.pk if parent else None})
        return category


class RequestTypeAccessPolicy:
    @staticmethod
    def category_path_active(category):
        seen=set()
        while category:
            if category.pk in seen or not category.is_active:return False
            seen.add(category.pk); category=category.parent
        return True

    @staticmethod
    def allows(request_type, employee, user=None, role_ids=None, permission_checked=False):
        if user and user.is_superuser: return True
        if not employee or not employee.is_active or (not permission_checked and not PermissionService.has_permission(employee=employee, permission="request.create")): return False
        rules = list(request_type.access_rules.all())
        if not rules: return True
        now=timezone.now()
        if role_ids is None: role_ids = set(EmployeeRole.objects.filter(employee=employee, is_active=True, role__is_active=True).filter(Q(active_from__isnull=True)|Q(active_from__lte=now),Q(active_until__isnull=True)|Q(active_until__gte=now)).values_list("role_id", flat=True))
        for rule in rules:
            if rule.scope_type == AccessScope.GLOBAL: return True
            if rule.scope_type == AccessScope.LEGAL_ENTITY and rule.legal_entity_id == employee.legal_entity_id: return True
            if rule.scope_type == AccessScope.ORG_UNIT and rule.org_unit_id == employee.org_unit_id: return True
            if rule.scope_type == AccessScope.LOCATION and rule.location_id == employee.primary_location_id: return True
            if rule.scope_type == AccessScope.ROLE and rule.role_id in role_ids: return True
        return False


class SchemaService:
    CONFIG_KEYS = {"min_length", "max_length", "min_value", "max_value", "same_legal_entity", "org_unit_id", "allow_inactive", "visible_if"}
    @classmethod
    def snapshot(cls, request_type):
        fields=[]; active_fields=list(request_type.fields.filter(is_active=True).prefetch_related("options")); keys={field.key for field in active_fields}
        if len(keys) != len(active_fields): raise CatalogError("Duplicate field key.")
        field_types={field.key:field.field_type for field in active_fields}
        for field in active_fields:
            unknown=set(field.config)-cls.CONFIG_KEYS
            if unknown: raise CatalogError(f"Unsupported config keys for {field.key}: {', '.join(sorted(unknown))}")
            options=[{"value":o.value,"label":o.label,"position":o.position} for o in field.options.filter(is_active=True)]
            if field.field_type in (FieldType.CHOICE, FieldType.MULTI_CHOICE) and not options: raise CatalogError(f"Choice field {field.key} has no active options.")
            cond=field.config.get("visible_if")
            if cond:
                if set(cond) != {"field","operator","value"} or str(cond["operator"]).upper() not in {"EQUALS","NOT_EQUALS"} or field_types.get(cond["field"]) not in {FieldType.CHOICE,FieldType.BOOLEAN} or cond["field"] == field.key:
                    raise CatalogError(f"Invalid visible_if for {field.key}.")
            fields.append({"key":field.key,"label":field.label,"help_text":field.help_text,"field_type":field.field_type,"required":field.required,"position":field.position,"default":field.default_value,"config":field.config,"options":options})
        return {"request_type":{"id":str(request_type.pk),"code":request_type.code,"name":request_type.name},"fields":fields}

    @classmethod
    @transaction.atomic
    def publish(cls, request_type, actor, user):
        require(actor,user,"request_type.publish")
        request_type=type(request_type).objects.select_for_update().get(pk=request_type.pk)
        payload=cls.snapshot(request_type)
        version=(request_type.schema_versions.aggregate(v=Max("version"))["v"] or 0)+1
        payload["schema_version"]=version
        schema=RequestTypeSchemaVersion.objects.create(request_type=request_type,version=version,schema_json=payload,created_by=actor)
        request_type.current_schema_version=schema; request_type.save(update_fields=["current_schema_version","updated_at"])
        AuditService.record(action="request_type.schema_published",entity=request_type,actor_user=user,actor_employee=actor,new_value={"version":version})
        DomainEventService.publish(event_type="request_type.schema_published",entity=request_type,actor=user,payload={"request_type_id":str(request_type.pk),"version":version})
        return schema


class RequestSchemaValidator:
    ENTITY_MODELS={FieldType.EMPLOYEE:Employee,FieldType.ORG_UNIT:OrgUnit,FieldType.LEGAL_ENTITY:LegalEntity,FieldType.LOCATION:Location}
    @staticmethod
    def visible(field,payload):
        cond=field.get("config",{}).get("visible_if")
        if not cond:return True
        equal=payload.get(cond["field"])==cond["value"]
        return equal if cond["operator"].upper()=="EQUALS" else not equal
    @classmethod
    def validate(cls,schema_version,payload,employee=None):
        cleaned={}; errors={}; known={f["key"] for f in schema_version.schema_json["fields"]}
        for unknown in set(payload)-known: errors[unknown]=["Unknown field."]
        for field in schema_version.schema_json["fields"]:
            key=field["key"]
            if not cls.visible(field,payload): continue
            value=payload.get(key,field.get("default"))
            if value in (None,""):
                if field["required"]: errors[key]=["Required field."]
                continue
            try: cleaned[key]=cls._value(field,value,employee)
            except (ValueError,TypeError,InvalidOperation) as exc: errors[key]=[str(exc) or "Invalid value."]
        if errors: raise CatalogError({"fields":errors})
        return cleaned
    @classmethod
    def _value(cls,f,v,employee):
        t,c=f["field_type"],f.get("config",{})
        if t in (FieldType.TEXT,FieldType.TEXTAREA,FieldType.FILE):
            if not isinstance(v,str): raise ValueError("Must be a string.")
            if c.get("min_length") is not None and len(v)<int(c["min_length"]): raise ValueError("Too short.")
            if c.get("max_length") is not None and len(v)>int(c["max_length"]): raise ValueError("Too long.")
        elif t==FieldType.INTEGER:
            if isinstance(v,bool): raise ValueError("Must be an integer.")
            v=int(v)
            if c.get("min_value") is not None and v<int(c["min_value"]): raise ValueError("Below minimum.")
            if c.get("max_value") is not None and v>int(c["max_value"]): raise ValueError("Above maximum.")
        elif t==FieldType.DECIMAL:
            v=Decimal(str(v)); lo=c.get("min_value"); hi=c.get("max_value")
            if lo is not None and v<Decimal(str(lo)): raise ValueError("Below minimum.")
            if hi is not None and v>Decimal(str(hi)): raise ValueError("Above maximum.")
            v=str(v)
        elif t==FieldType.BOOLEAN:
            if not isinstance(v,bool): raise ValueError("Must be boolean.")
        elif t==FieldType.DATE:
            if not isinstance(v,str) or not parse_date(v): raise ValueError("Invalid date.")
        elif t==FieldType.DATETIME:
            dt=parse_datetime(v) if isinstance(v,str) else None
            if not dt or not dt.tzinfo: raise ValueError("Timezone-aware datetime required.")
        elif t in (FieldType.CHOICE,FieldType.MULTI_CHOICE):
            allowed={o["value"] for o in f.get("options",[])}
            vals=v if t==FieldType.MULTI_CHOICE else [v]
            if not isinstance(vals,list) or len(vals)!=len(set(vals)) or not set(vals)<=allowed: raise ValueError("Unknown or duplicate choice.")
        elif t in cls.ENTITY_MODELS:
            uid=UUID(str(v)); obj=cls.ENTITY_MODELS[t].objects.filter(pk=uid).first()
            if not obj: raise ValueError("Entity not found.")
            if hasattr(obj,"is_active") and not c.get("allow_inactive") and not obj.is_active: raise ValueError("Entity is inactive.")
            if c.get("same_legal_entity") and employee and getattr(obj,"legal_entity_id",None)!=employee.legal_entity_id: raise ValueError("Entity is outside legal entity.")
            if c.get("org_unit_id") and str(getattr(obj,"org_unit_id",None))!=str(c["org_unit_id"]): raise ValueError("Entity is outside org unit.")
            v=str(uid)
        return v
