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
from employees.assignment import AssignmentResolver, AssignmentTargetAmbiguous, AssignmentTargetUnresolved
from .exceptions import RequestBusinessError, RequestVersionConflict
from .state_machine import ServiceRequestStateMachine
from .models import (AccessScope, FieldType, RequestTypeSchemaVersion, RequestNumberSequence, RequestRoutingRule,
    ServiceRequest, ServiceRequestFieldValue, ServiceRequestStatusHistory, ServiceRequestAssignmentHistory,
    ServiceRequestWaitingPeriod, ServiceRequestRelation, ServiceRequestTask, ServiceRequestFieldRevision, RequestStatus, RequestType)


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


class ServiceRequestService:
    @staticmethod
    def _authorize(actor,user,permission,obj=None):
        from .policies import ServiceRequestAccessPolicy
        if not (user and user.is_superuser) and not ServiceRequestAccessPolicy.allows(employee=actor,permission=permission,request=obj):
            raise PermissionDenied("Insufficient permissions.")
    @staticmethod
    def _next_number():
        seq,_=RequestNumberSequence.objects.select_for_update().get_or_create(key="request"); seq.value+=1; seq.save(update_fields=["value"]); return f"REQ-{seq.value:06d}"
    @staticmethod
    def _resolve_one(target):
        try: employees=AssignmentResolver.resolve(target)
        except AssignmentTargetUnresolved as exc: raise RequestBusinessError(str(exc),code="request_assignment_unresolved") from exc
        except AssignmentTargetAmbiguous as exc: raise RequestBusinessError(str(exc),code="request_assignment_ambiguous") from exc
        if len(employees)!=1: raise RequestBusinessError("Assignment must resolve to one employee.",code="request_assignment_ambiguous")
        return employees[0]
    @classmethod
    def _locked(cls,obj,version):
        locked=ServiceRequest.objects.select_for_update().get(pk=obj.pk)
        if locked.version!=version: raise RequestVersionConflict("Request was changed by another user.")
        return locked
    @staticmethod
    def _record(obj,actor,user,action,old=None,new=None):
        AuditService.record(action=action,entity=obj,actor_user=user,actor_employee=actor,old_value=old,new_value=new)
        DomainEventService.publish(event_type=action,entity=obj,actor=user,payload={"request_id":str(obj.pk),"number":obj.number,"status":obj.status})
    @classmethod
    def _route(cls,request_type,requester,priority):
        rules=request_type.routing_rules.filter(is_active=True).filter(Q(legal_entity__isnull=True)|Q(legal_entity=requester.legal_entity),Q(org_unit__isnull=True)|Q(org_unit=requester.org_unit),Q(location__isnull=True)|Q(location=requester.primary_location),Q(priority="")|Q(priority=priority)).order_by("order","id")
        first=rules.first()
        if not first:return None
        if rules.filter(order=first.order).count()>1: raise RequestBusinessError("Several routing rules have the same priority.",code="request_routing_ambiguous")
        return first.target
    @classmethod
    @transaction.atomic
    def create(cls,*,actor,actor_user,request_type,subject,payload,requester=None,description="",priority=None):
        cls._authorize(actor,actor_user,"request.create")
        requester=requester or actor
        if requester!=actor:cls._authorize(actor,actor_user,"request.create_for_others")
        request_type=RequestType.objects.select_related("service__category","current_schema_version").get(pk=request_type.pk)
        if not request_type.is_active or not request_type.service.is_active or not request_type.current_schema_version_id or not RequestTypeAccessPolicy.category_path_active(request_type.service.category) or not RequestTypeAccessPolicy.allows(request_type,requester,actor_user):
            raise RequestBusinessError("Request type is unavailable.",code="request_type_unavailable")
        cleaned=RequestSchemaValidator.validate(request_type.current_schema_version,payload,requester); priority=priority or request_type.default_priority
        target=cls._route(request_type,requester,priority); employee=cls._resolve_one(target) if target else None; now=timezone.now()
        obj=ServiceRequest.objects.create(number=cls._next_number(),request_type=request_type,schema_version=request_type.current_schema_version,requester=requester,created_by=actor_user,updated_by=actor_user,subject=subject,description=description,priority=priority,status=RequestStatus.ASSIGNED if employee else RequestStatus.NEW,service=request_type.service,category=request_type.service.category,assigned_target=target,assigned_employee=employee,responsible_target=target,responsible_employee=employee,org_unit=requester.org_unit,legal_entity=requester.legal_entity,location=requester.primary_location,routing_unresolved=not bool(target),submitted_at=now,assigned_at=now if employee else None)
        fields={f["key"]:f for f in request_type.current_schema_version.schema_json["fields"]}
        ServiceRequestFieldValue.objects.bulk_create([ServiceRequestFieldValue(request=obj,field_key=k,field_type=fields[k]["field_type"],label=fields[k]["label"],value_json=v) for k,v in cleaned.items()])
        ServiceRequestStatusHistory.objects.create(request=obj,to_status=obj.status,actor=actor)
        if target:ServiceRequestAssignmentHistory.objects.create(request=obj,new_target=target,new_employee=employee,changed_by=actor,reason="Automatic routing")
        cls._record(obj,actor,actor_user,"request.created",new={"status":obj.status,"schema_version":obj.schema_version.version})
        from sla.runtime import SLAInstanceService
        SLAInstanceService.create_for_request(obj,actor=actor,actor_user=actor_user)
        return obj
    @classmethod
    @transaction.atomic
    def assign(cls,*,request,actor,actor_user,version,target,reason="",reassign=False):
        request=cls._locked(request,version); cls._authorize(actor,actor_user,"request.reassign" if reassign else "request.assign",request)
        if reassign and request.status in {RequestStatus.IN_PROGRESS,RequestStatus.WAITING_REQUESTER,RequestStatus.WAITING_EXTERNAL,RequestStatus.RESOLVED} and not reason:raise RequestBusinessError("Reassignment reason is required.",code="request_reassign_reason_required")
        employee=cls._resolve_one(target); old_status=request.status
        if request.status==RequestStatus.NEW:ServiceRequestStateMachine.validate(request.status,RequestStatus.ASSIGNED); request.status=RequestStatus.ASSIGNED
        ServiceRequestAssignmentHistory.objects.create(request=request,old_target=request.assigned_target,old_employee=request.assigned_employee,new_target=target,new_employee=employee,changed_by=actor,reason=reason)
        request.assigned_target=target; request.assigned_employee=employee; request.routing_unresolved=False; request.assigned_at=request.assigned_at or timezone.now(); request.version+=1; request.updated_by=actor_user; request.save()
        if old_status!=request.status:ServiceRequestStatusHistory.objects.create(request=request,from_status=old_status,to_status=request.status,actor=actor,reason=reason)
        cls._record(request,actor,actor_user,"request.reassigned" if reassign else "request.assigned"); return request
    @classmethod
    @transaction.atomic
    def update(cls,*,request,actor,actor_user,version,payload=None,**changes):
        request=cls._locked(request,version);cls._authorize(actor,actor_user,"request.edit",request)
        if request.status in {RequestStatus.RESOLVED,RequestStatus.CLOSED,RequestStatus.CANCELLED}:raise RequestBusinessError("Final request is immutable.",code="request_immutable")
        if set(changes)-{"subject","description","priority"}:raise RequestBusinessError("Protected request fields cannot be patched.",code="request_field_read_only")
        if payload is not None:
            if request.status not in {RequestStatus.NEW,RequestStatus.ASSIGNED}:raise RequestBusinessError("Dynamic values can only be edited before work starts.",code="request_payload_immutable")
            old={v.field_key:v.value_json for v in request.field_values.all()};merged={**old,**payload};cleaned=RequestSchemaValidator.validate(request.schema_version,merged,request.requester)
            definitions={f["key"]:f for f in request.schema_version.schema_json["fields"]}
            request.field_values.all().delete()
            ServiceRequestFieldValue.objects.bulk_create([ServiceRequestFieldValue(request=request,field_key=k,field_type=definitions[k]["field_type"],label=definitions[k]["label"],value_json=v) for k,v in cleaned.items()])
            ServiceRequestFieldRevision.objects.create(request=request,old_values=old,new_values=cleaned,changed_by=actor)
        old_core={k:getattr(request,k) for k in changes}
        for key,value in changes.items():setattr(request,key,value)
        request.version+=1;request.updated_by=actor_user;request.save(update_fields=[*changes,"version","updated_by","updated_at"]);cls._record(request,actor,actor_user,"request.updated",old=old_core,new={k:getattr(request,k) for k in changes});return request
    @classmethod
    def _transition(cls,*,request,actor,actor_user,version,to_status,permission,reason=""):
        request=cls._locked(request,version); cls._authorize(actor,actor_user,permission,request); old=request.status; ServiceRequestStateMachine.validate(old,to_status); now=timezone.now()
        if to_status==RequestStatus.IN_PROGRESS: request.started_at=request.started_at or now
        if to_status==RequestStatus.RESOLVED: request.resolved_at=now
        if to_status==RequestStatus.CLOSED: request.closed_at=now
        if to_status==RequestStatus.CANCELLED: request.cancelled_at=now
        request.status=to_status; request.version+=1; request.updated_by=actor_user; request.save(); ServiceRequestStatusHistory.objects.create(request=request,from_status=old,to_status=to_status,actor=actor,reason=reason); cls._record(request,actor,actor_user,f"request.{to_status}",old={"status":old},new={"status":to_status})
        from sla.runtime import SLAInstanceService
        SLAInstanceService.handle_lifecycle(request,event_at=now,actor=actor,actor_user=actor_user,previous_status=old)
        return request
    @classmethod
    @transaction.atomic
    def start(cls,**kw):return cls._transition(to_status=RequestStatus.IN_PROGRESS,permission="request.start",**kw)
    @classmethod
    @transaction.atomic
    def wait(cls,*,waiting_type,comment,**kw):
        if waiting_type not in {RequestStatus.WAITING_REQUESTER,RequestStatus.WAITING_EXTERNAL} or not comment:raise RequestBusinessError("Waiting comment is required.",code="request_wait_reason_required")
        obj=cls._transition(to_status=waiting_type,permission="request.wait",reason=comment,**kw); ServiceRequestWaitingPeriod.objects.create(request=obj,waiting_type=waiting_type,comment=comment,started_by=kw["actor"]); return obj
    @classmethod
    @transaction.atomic
    def resume(cls,**kw):
        obj=cls._transition(to_status=RequestStatus.IN_PROGRESS,permission="request.start",**kw); period=obj.waiting_periods.filter(ended_at__isnull=True).first()
        if period:period.ended_at=timezone.now();period.ended_by=kw["actor"];period.save(update_fields=["ended_at","ended_by"])
        return obj
    @classmethod
    @transaction.atomic
    def resolve(cls,*,resolution_code,resolution_comment,duplicate_of=None,**kw):
        if not resolution_comment:raise RequestBusinessError("Resolution comment is required.",code="request_resolution_comment_required")
        request=ServiceRequest.objects.get(pk=kw["request"].pk); execution=request.task_links.filter(relation_type=ServiceRequestTask.Type.EXECUTION)
        if request.request_type.task_completion_policy==RequestType.TaskCompletionPolicy.ALL_COMPLETED and execution.exclude(task__status="completed").exists():raise RequestBusinessError("Execution tasks are incomplete.",code="request_tasks_incomplete")
        if request.request_type.task_completion_policy==RequestType.TaskCompletionPolicy.ALL_TERMINAL and execution.exclude(task__status__in=["completed","cancelled"]).exists():raise RequestBusinessError("Execution tasks are not terminal.",code="request_tasks_incomplete")
        obj=cls._transition(to_status=RequestStatus.RESOLVED,permission="request.resolve",reason=resolution_comment,**kw); obj.resolution_code=resolution_code;obj.resolution_comment=resolution_comment;obj.save(update_fields=["resolution_code","resolution_comment","updated_at"])
        if resolution_code.upper()=="DUPLICATE" and duplicate_of:
            if duplicate_of.pk==obj.pk or duplicate_of.outgoing_relations.filter(to_request=obj,relation_type=ServiceRequestRelation.Type.DUPLICATE_OF).exists():raise RequestBusinessError("Duplicate relation cycle.",code="request_duplicate_cycle")
            ServiceRequestRelation.objects.create(from_request=obj,to_request=duplicate_of,relation_type=ServiceRequestRelation.Type.DUPLICATE_OF)
        return obj
    @classmethod
    @transaction.atomic
    def close(cls,**kw):return cls._transition(to_status=RequestStatus.CLOSED,permission="request.close",**kw)
    @classmethod
    @transaction.atomic
    def reopen(cls,**kw):
        if not kw.get("reason"):raise RequestBusinessError("Reopen reason is required.",code="request_reopen_reason_required")
        obj=cls._transition(to_status=RequestStatus.IN_PROGRESS,permission="request.reopen",**kw);obj.reopened_at=timezone.now();obj.save(update_fields=["reopened_at","updated_at"]);return obj
    @classmethod
    @transaction.atomic
    def cancel(cls,**kw):
        if not kw.get("reason"):raise RequestBusinessError("Cancellation reason is required.",code="request_cancel_reason_required")
        obj=cls._transition(to_status=RequestStatus.CANCELLED,permission="request.cancel",**kw);obj.cancellation_reason=kw["reason"];obj.save(update_fields=["cancellation_reason","updated_at"]);return obj


class ServiceRequestTaskService:
    @classmethod
    @transaction.atomic
    def create_task(cls,*,request,actor,actor_user,version,relation_type=ServiceRequestTask.Type.EXECUTION,template=None,**data):
        request=ServiceRequestService._locked(request,version);ServiceRequestService._authorize(actor,actor_user,"request.task_create",request)
        if template:
            from work_tasks.automation import TaskTemplateService
            task=TaskTemplateService.create_task(template=template,actor=actor,actor_user=actor_user,**data)
            task.source_type="request";task.source_id=str(request.pk);task.save(update_fields=["source_type","source_id","updated_at"])
        else:
            from work_tasks.services import TaskService
            task=TaskService.create(actor=actor,actor_user=actor_user,source_type="request",source_id=str(request.pk),**data)
        ServiceRequestTask.objects.create(request=request,task=task,relation_type=relation_type,created_by=actor_user);request.version+=1;request.updated_by=actor_user;request.save(update_fields=["version","updated_by","updated_at"]);ServiceRequestService._record(request,actor,actor_user,"request.task_created",new={"task_id":str(task.pk)});return task
