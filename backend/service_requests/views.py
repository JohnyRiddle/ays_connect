from django.db import transaction
from django.db.models import Prefetch
from django.db.models import Q
from django.utils import timezone
from django.http import FileResponse
from access_control.models import EmployeeRole
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError, MethodNotAllowed
from rest_framework.response import Response
from rest_framework.views import APIView
from audit.services import AuditService
from events.services import DomainEventService
from .models import ServiceCategory, Service, RequestType, RequestTypeAccessRule, RequestFieldDefinition, RequestFieldOption, ServiceRequest, RequestRoutingRule, RequestStatus, ServiceRequestComment, ServiceRequestAttachment, CollaborationVisibility
from .serializers import CategorySerializer, ServiceSerializer, RequestTypeSerializer, AccessRuleSerializer, FieldSerializer, OptionSerializer, SchemaVersionSerializer, RoutingRuleSerializer, ServiceRequestSerializer, RequestCreateSerializer, RequestTaskLinkSerializer, RequestCommentSerializer, RequestCommentWriteSerializer, RequestAttachmentSerializer, RequestWatcherSerializer, RequestWatcherWriteSerializer
from .services import CategoryService, RequestTypeAccessPolicy, SchemaService, require, CatalogError, ServiceRequestService, ServiceRequestTaskService
from .policies import ServiceRequestAccessPolicy
from .collaboration import RequestCollaborationService
from .activity import ServiceRequestActivitySelector
from employees.models import AssignmentTarget, Employee


class ActorMixin:
    def actor(self):
        try:return self.request.user.employee
        except Exception: raise ValidationError("Authenticated user has no employee profile.")
    def manage(self, permission="service_catalog.manage"): require(self.actor(),self.request.user,permission)
    def initial(self,request,*args,**kwargs):
        super().initial(request,*args,**kwargs)
        if getattr(self,"action",None) in {None,"form_schema"}: return
        if getattr(self,"action",None)=="publish_schema": return require(self.actor(),request.user,"request_type.publish")
        permission=getattr(self,"read_permission","service_catalog.view") if request.method in {"GET","HEAD","OPTIONS"} else getattr(self,"write_permission","service_catalog.manage")
        require(self.actor(),request.user,permission)


class CategoryViewSet(ActorMixin,viewsets.ModelViewSet):
    queryset=ServiceCategory.objects.select_related("parent"); serializer_class=CategorySerializer; http_method_names=["get","post","patch","head","options"]
    def perform_create(self,s):
        self.manage(); CategoryService.validate_parent(None,s.validated_data.get("parent")); obj=s.save(); AuditService.record(action="service_category.created",entity=obj,actor_user=self.request.user,actor_employee=self.actor())
    def perform_update(self,s):
        self.manage(); CategoryService.validate_parent(self.get_object(),s.validated_data.get("parent",self.get_object().parent)); obj=s.save(); AuditService.record(action="service_category.updated",entity=obj,actor_user=self.request.user,actor_employee=self.actor())
    @action(detail=True,methods=["post"])
    def move(self,request,pk=None):
        parent=get_object_or_404(ServiceCategory,pk=request.data["parent"]) if request.data.get("parent") else None
        return Response(self.get_serializer(CategoryService.move(self.get_object(),parent,self.actor(),request.user)).data)
    @action(detail=True,methods=["post"])
    def deactivate(self,request,pk=None):
        self.manage(); obj=self.get_object(); obj.is_active=False; obj.save(update_fields=["is_active","updated_at"]); AuditService.record(action="service_category.deactivated",entity=obj,actor_user=request.user,actor_employee=self.actor()); return Response(self.get_serializer(obj).data)


class ServiceViewSet(ActorMixin,viewsets.ModelViewSet):
    queryset=Service.objects.select_related("category","owner_org_unit","owner_functional_group","legal_entity","location"); serializer_class=ServiceSerializer; http_method_names=["get","post","patch","head","options"]
    def _record(self,obj,action,event):
        AuditService.record(action=action,entity=obj,actor_user=self.request.user,actor_employee=self.actor()); DomainEventService.publish(event_type=event,entity=obj,actor=self.request.user,payload={"id":str(obj.pk)})
    def perform_create(self,s): self.manage(); self._record(s.save(),"service.created","service.created")
    def perform_update(self,s): self.manage(); self._record(s.save(),"service.updated","service.updated")
    @action(detail=True,methods=["post"])
    def deactivate(self,request,pk=None):
        self.manage(); obj=self.get_object(); obj.is_active=False; obj.save(update_fields=["is_active","updated_at"]); self._record(obj,"service.deactivated","service.updated"); return Response(self.get_serializer(obj).data)


class RequestTypeViewSet(ActorMixin,viewsets.ModelViewSet):
    read_permission="request_type.view"; write_permission="request_type.manage"
    queryset=RequestType.objects.select_related("service__category","current_schema_version","created_by").prefetch_related("access_rules","fields__options"); serializer_class=RequestTypeSerializer; http_method_names=["get","post","patch","head","options"]
    def _record(self,obj,action,event=None):
        AuditService.record(action=action,entity=obj,actor_user=self.request.user,actor_employee=self.actor())
        if event: DomainEventService.publish(event_type=event,entity=obj,actor=self.request.user,payload={"id":str(obj.pk)})
    def perform_create(self,s): self.manage("request_type.manage"); self._record(s.save(created_by=self.actor()),"request_type.created","request_type.created")
    def perform_update(self,s): self.manage("request_type.manage"); self._record(s.save(),"request_type.updated","request_type.updated")
    @action(detail=True,methods=["post"],url_path="deactivate")
    def deactivate(self,request,pk=None):
        self.manage("request_type.manage"); obj=self.get_object(); obj.is_active=False; obj.save(update_fields=["is_active","updated_at"]); self._record(obj,"request_type.deactivated","request_type.deactivated"); return Response(self.get_serializer(obj).data)
    @action(detail=True,methods=["get","post"],url_path="fields")
    def fields(self,request,pk=None):
        obj=self.get_object()
        if request.method=="GET": return Response(FieldSerializer(obj.fields.all(),many=True).data)
        self.manage("request_type.manage"); s=FieldSerializer(data=request.data); s.is_valid(raise_exception=True); field=s.save(request_type=obj); self._record(obj,"request_type.field_created"); return Response(FieldSerializer(field).data,status=201)
    @action(detail=True,methods=["patch"],url_path=r"fields/(?P<field_id>[^/.]+)")
    def field_detail(self,request,pk=None,field_id=None):
        self.manage("request_type.manage"); field=get_object_or_404(self.get_object().fields,pk=field_id); s=FieldSerializer(field,data=request.data,partial=True); s.is_valid(raise_exception=True); s.save(); self._record(self.get_object(),"request_type.field_updated"); return Response(s.data)
    @action(detail=True,methods=["get","post"],url_path=r"fields/(?P<field_id>[^/.]+)/options")
    def options(self,request,pk=None,field_id=None):
        field=get_object_or_404(self.get_object().fields,pk=field_id)
        if request.method=="GET":return Response(OptionSerializer(field.options.all(),many=True).data)
        self.manage("request_type.manage"); s=OptionSerializer(data=request.data); s.is_valid(raise_exception=True); return Response(OptionSerializer(s.save(field=field)).data,status=201)
    @action(detail=True,methods=["patch"],url_path=r"fields/(?P<field_id>[^/.]+)/options/(?P<option_id>[^/.]+)")
    def option_detail(self,request,pk=None,field_id=None,option_id=None):
        self.manage("request_type.manage"); field=get_object_or_404(self.get_object().fields,pk=field_id); opt=get_object_or_404(field.options,pk=option_id); s=OptionSerializer(opt,data=request.data,partial=True); s.is_valid(raise_exception=True); s.save(); return Response(s.data)
    @action(detail=True,methods=["get","post"],url_path="access-rules")
    def access_rules(self,request,pk=None):
        obj=self.get_object()
        if request.method=="GET":return Response(AccessRuleSerializer(obj.access_rules.all(),many=True).data)
        self.manage("request_type.manage"); s=AccessRuleSerializer(data=request.data); s.is_valid(raise_exception=True); rule=s.save(request_type=obj); return Response(AccessRuleSerializer(rule).data,status=201)
    @action(detail=True,methods=["post"],url_path="publish-schema")
    def publish_schema(self,request,pk=None):
        try:schema=SchemaService.publish(self.get_object(),self.actor(),request.user)
        except CatalogError as exc:raise ValidationError(str(exc))
        return Response(SchemaVersionSerializer(schema).data,status=201)
    @action(detail=True,methods=["get"],url_path="form-schema")
    def form_schema(self,request,pk=None):
        obj=self.get_object()
        if not obj.is_active or not obj.service.is_active or not RequestTypeAccessPolicy.category_path_active(obj.service.category) or not obj.current_schema_version_id or not RequestTypeAccessPolicy.allows(obj,self.actor(),request.user): raise NotFound()
        return Response(obj.current_schema_version.schema_json)
    @action(detail=True,methods=["get","post"],url_path="routing-rules")
    def routing_rules(self,request,pk=None):
        self.manage("request_routing.view" if request.method=="GET" else "request_routing.manage");obj=self.get_object()
        if request.method=="GET":return Response(RoutingRuleSerializer(obj.routing_rules.all(),many=True).data)
        s=RoutingRuleSerializer(data=request.data);s.is_valid(raise_exception=True);rule=s.save(request_type=obj);self._record(rule,"request_routing.created");return Response(RoutingRuleSerializer(rule).data,status=201)
    @action(detail=True,methods=["patch","delete"],url_path=r"routing-rules/(?P<rule_id>[^/.]+)")
    def routing_rule_detail(self,request,pk=None,rule_id=None):
        self.manage("request_routing.manage");rule=get_object_or_404(self.get_object().routing_rules,pk=rule_id)
        if request.method=="DELETE":rule.is_active=False;rule.save(update_fields=["is_active","updated_at"]);self._record(rule,"request_routing.deactivated");return Response(status=204)
        s=RoutingRuleSerializer(rule,data=request.data,partial=True);s.is_valid(raise_exception=True);s.save();self._record(rule,"request_routing.updated");return Response(s.data)


class ServiceCatalogView(ActorMixin,APIView):
    def get(self,request):
        actor=self.actor(); require(actor,request.user,"request.create")
        types=RequestType.objects.filter(is_active=True,current_schema_version__isnull=False,service__is_active=True,service__category__is_active=True).select_related("service__category").prefetch_related("access_rules")
        all_category_objects={c.pk:c for c in ServiceCategory.objects.all()}
        def active_path(category_id):
            seen=set()
            while category_id:
                if category_id in seen:return False
                seen.add(category_id); category=all_category_objects.get(category_id)
                if not category or not category.is_active:return False
                category_id=category.parent_id
            return True
        now=timezone.now(); role_ids=set(EmployeeRole.objects.filter(employee=actor,is_active=True,role__is_active=True).filter(Q(active_from__isnull=True)|Q(active_from__lte=now),Q(active_until__isnull=True)|Q(active_until__gte=now)).values_list("role_id",flat=True))
        allowed=[x for x in types if active_path(x.service.category_id) and RequestTypeAccessPolicy.allows(x,actor,request.user,role_ids=role_ids,permission_checked=True)]
        services={}; direct_categories=set()
        for rt in allowed:
            service=rt.service; category=service.category
            services.setdefault(service.pk,{"id":str(service.pk),"name":service.name,"position":service.position,"request_types":[],"_category_id":category.pk})["request_types"].append({"id":str(rt.pk),"name":rt.name,"code":rt.code,"position":rt.position})
            direct_categories.add(category.pk)
        all_categories={pk:c for pk,c in all_category_objects.items() if c.is_active}
        included=set(direct_categories)
        for category_id in list(direct_categories):
            current=all_categories.get(category_id)
            while current and current.parent_id in all_categories:
                included.add(current.parent_id); current=all_categories[current.parent_id]
        nodes={pk:{"id":str(pk),"name":all_categories[pk].name,"position":all_categories[pk].position,"services":[],"children":[]} for pk in included}
        for service in services.values(): category_id=service.pop("_category_id"); nodes[category_id]["services"].append(service)
        roots=[]
        for pk,node in nodes.items():
            parent_id=all_categories[pk].parent_id
            (nodes[parent_id]["children"] if parent_id in nodes else roots).append(node)
        def sort_tree(items):
            items.sort(key=lambda x:(x["position"],x["name"],x["id"]))
            for item in items:
                item["services"].sort(key=lambda x:(x["position"],x["name"],x["id"])); sort_tree(item["children"])
        sort_tree(roots); return Response(roots)


class ServiceRequestViewSet(viewsets.ModelViewSet):
    serializer_class=ServiceRequestSerializer;http_method_names=["get","post","patch","delete","head","options"]
    def destroy(self,request,*args,**kwargs):raise MethodNotAllowed("DELETE")
    def actor(self):
        try:return self.request.user.employee
        except Exception:raise ValidationError("Authenticated user has no employee profile.")
    def get_queryset(self):
        qs=ServiceRequest.objects.select_related("request_type","schema_version","service","category","requester","assigned_employee","responsible_employee","sla_instance__policy_version__policy").prefetch_related("field_values","task_links__task","comments","attachments","watcher_records__employee","sla_instance__metrics__resolution_cycle")
        if not self.request.user.is_superuser:qs=qs.filter(ServiceRequestAccessPolicy.visibility_query(employee=self.actor())).distinct()
        params=self.request.query_params
        for key in ("status","priority","request_type","service","requester","assigned_employee","responsible_employee","org_unit","legal_entity","location"):
            if params.get(key):qs=qs.filter(**{key:params[key]})
        if params.get("created_from"):qs=qs.filter(created_at__gte=params["created_from"])
        if params.get("created_to"):qs=qs.filter(created_at__lte=params["created_to"])
        if params.get("resolved_from"):qs=qs.filter(resolved_at__gte=params["resolved_from"])
        if params.get("resolved_to"):qs=qs.filter(resolved_at__lte=params["resolved_to"])
        if params.get("has_sla") in {"true","false"}:qs=qs.filter(sla_instance__isnull=params["has_sla"]=="false")
        if params.get("sla_response_breached") in {"true","false"}:qs=qs.filter(sla_instance__metrics__metric_type="response",sla_instance__metrics__breached_at__isnull=params["sla_response_breached"]=="false")
        if params.get("sla_resolution_breached") in {"true","false"}:qs=qs.filter(sla_instance__metrics__metric_type="resolution",sla_instance__metrics__breached_at__isnull=params["sla_resolution_breached"]=="false")
        if params.get("sla_resolution_paused") in {"true","false"}:qs=qs.filter(sla_instance__status="paused" if params["sla_resolution_paused"]=="true" else "active")
        if params.get("search"):qs=qs.filter(Q(number__icontains=params["search"])|Q(subject__icontains=params["search"])|Q(description__icontains=params["search"]))
        ordering=params.get("ordering","-created_at");allowed={"created_at","updated_at","priority","number","resolved_at"};field=ordering.lstrip("-")
        return qs.order_by(ordering if field in allowed else "-created_at")
    def create(self,request,*args,**kwargs):
        s=RequestCreateSerializer(data=request.data);s.is_valid(raise_exception=True);obj=ServiceRequestService.create(actor=self.actor(),actor_user=request.user,**s.validated_data);return Response(ServiceRequestSerializer(obj,context=self.get_serializer_context()).data,status=201)
    def partial_update(self,request,*args,**kwargs):
        allowed={"subject","description","priority","payload","version"}
        if set(request.data)-allowed:raise ValidationError("Protected request fields cannot be patched.")
        data={k:v for k,v in request.data.items() if k not in {"version","payload"}}
        obj=ServiceRequestService.update(request=self.get_object(),actor=self.actor(),actor_user=request.user,version=request.data.get("version"),payload=request.data.get("payload") if "payload" in request.data else None,**data);return Response(self.get_serializer(obj).data)
    def _call(self,request,method,**extra):
        obj=getattr(ServiceRequestService,method)(request=self.get_object(),actor=self.actor(),actor_user=request.user,version=request.data.get("version"),**extra);return Response(self.get_serializer(obj).data)
    @action(detail=True,methods=["post"])
    def assign(self,request,pk=None):return self._call(request,"assign",target=get_object_or_404(AssignmentTarget,pk=request.data.get("target")),reason=request.data.get("reason",""))
    @action(detail=True,methods=["post"])
    def reassign(self,request,pk=None):return self._call(request,"assign",target=get_object_or_404(AssignmentTarget,pk=request.data.get("target")),reason=request.data.get("reason",""),reassign=True)
    @action(detail=True,methods=["post"])
    def start(self,request,pk=None):return self._call(request,"start",reason=request.data.get("reason",""))
    @action(detail=True,methods=["post"],url_path="wait-requester")
    def wait_requester(self,request,pk=None):return self._call(request,"wait",waiting_type=RequestStatus.WAITING_REQUESTER,comment=request.data.get("comment",""))
    @action(detail=True,methods=["post"],url_path="wait-external")
    def wait_external(self,request,pk=None):return self._call(request,"wait",waiting_type=RequestStatus.WAITING_EXTERNAL,comment=request.data.get("comment",""))
    @action(detail=True,methods=["post"])
    def resume(self,request,pk=None):return self._call(request,"resume",reason=request.data.get("reason",""))
    @action(detail=True,methods=["post"])
    def resolve(self,request,pk=None):
        duplicate=ServiceRequest.objects.filter(pk=request.data.get("duplicate_of")).first() if request.data.get("duplicate_of") else None
        return self._call(request,"resolve",resolution_code=request.data.get("resolution_code","RESOLVED"),resolution_comment=request.data.get("resolution_comment",""),duplicate_of=duplicate)
    @action(detail=True,methods=["post"])
    def close(self,request,pk=None):return self._call(request,"close",reason=request.data.get("reason",""))
    @action(detail=True,methods=["post"])
    def reopen(self,request,pk=None):return self._call(request,"reopen",reason=request.data.get("reason",""))
    @action(detail=True,methods=["post"])
    def cancel(self,request,pk=None):return self._call(request,"cancel",reason=request.data.get("reason",""))
    @action(detail=True,methods=["get","post"])
    def tasks(self,request,pk=None):
        obj=self.get_object()
        if request.method=="GET":return Response(RequestTaskLinkSerializer(obj.task_links.select_related("task"),many=True).data)
        data=request.data.copy();version=data.pop("version",None);template_id=data.pop("template",None);relation=data.pop("relation_type","execution")
        template=get_object_or_404(__import__('work_tasks.models',fromlist=['TaskTemplate']).TaskTemplate,pk=template_id) if template_id else None
        task=ServiceRequestTaskService.create_task(request=obj,actor=self.actor(),actor_user=request.user,version=version,relation_type=relation,template=template,**data);return Response({"id":str(task.pk),"number":task.number},status=201)
    @action(detail=True,methods=["get"])
    def history(self,request,pk=None):
        obj=self.get_object();return Response({"status":[{"from_status":x.from_status,"to_status":x.to_status,"reason":x.reason,"created_at":x.created_at} for x in obj.status_history.all()],"assignments":[{"old_employee":str(x.old_employee_id or ""),"new_employee":str(x.new_employee_id),"reason":x.reason,"created_at":x.created_at} for x in obj.assignment_history.all()],"waiting":[{"type":x.waiting_type,"comment":x.comment,"started_at":x.started_at,"ended_at":x.ended_at} for x in obj.waiting_periods.all()]})
    @action(detail=True,methods=["get"],url_path="sla")
    def sla_status(self,request,pk=None):
        from sla.serializers import SLAInstanceSerializer
        obj=self.get_object()
        try:instance=obj.sla_instance
        except Exception:return Response({"has_sla":False})
        return Response({"has_sla":True,**SLAInstanceSerializer(instance).data})
    @action(detail=True,methods=["get"],url_path="sla/history")
    def sla_history(self,request,pk=None):
        from sla.serializers import ResolutionCycleSerializer
        obj=self.get_object()
        try:instance=obj.sla_instance
        except Exception:return Response({"has_sla":False,"cycles":[],"thresholds":[]})
        thresholds=[{"metric_type":x.metric_instance.metric_type,"cycle":x.metric_instance.resolution_cycle.cycle_number if x.metric_instance.resolution_cycle_id else None,"threshold_percent":x.threshold_percent,"reached_at":x.reached_at} for x in instance.metrics.prefetch_related("threshold_events").all() for x in x.threshold_events.all()]
        return Response({"has_sla":True,"created_at":instance.created_at,"cycles":ResolutionCycleSerializer(instance.resolution_cycles.prefetch_related("pause_periods","metric"),many=True).data,"thresholds":thresholds})
    def _internal(self,obj,kind="comment"):return self.request.user.is_superuser or ServiceRequestAccessPolicy.can_view_internal(employee=self.actor(),request=obj,kind=kind)
    @action(detail=True,methods=["get","post"])
    def comments(self,request,pk=None):
        obj=self.get_object();qs=obj.comments.select_related("author","deleted_by").prefetch_related("mention_records__employee")
        if not self._internal(obj,"comment"):qs=qs.filter(visibility=CollaborationVisibility.PUBLIC)
        if request.method=="GET":return Response(RequestCommentSerializer(qs,many=True).data)
        s=RequestCommentWriteSerializer(data=request.data);s.is_valid(raise_exception=True);comment=RequestCollaborationService.add_comment(request=obj,actor=self.actor(),actor_user=request.user,**s.validated_data);return Response(RequestCommentSerializer(comment).data,status=201)
    @action(detail=True,methods=["patch","delete"],url_path=r"comments/(?P<comment_id>[^/.]+)")
    def comment_detail(self,request,pk=None,comment_id=None):
        obj=self.get_object();qs=ServiceRequestComment.objects.select_related("request")
        if not self._internal(obj,"comment"):qs=qs.filter(visibility=CollaborationVisibility.PUBLIC)
        comment=get_object_or_404(qs,pk=comment_id,request=obj)
        if request.method=="DELETE":RequestCollaborationService.delete_comment(comment=comment,actor=self.actor(),actor_user=request.user);return Response(status=204)
        if "visibility" in request.data:raise ValidationError("Comment visibility is immutable.")
        s=RequestCommentWriteSerializer(data=request.data);s.is_valid(raise_exception=True);comment=RequestCollaborationService.edit_comment(comment=comment,actor=self.actor(),actor_user=request.user,body=s.validated_data["body"],mentions=s.validated_data.get("mentions",()));return Response(RequestCommentSerializer(comment).data)
    @action(detail=True,methods=["get","post"])
    def attachments(self,request,pk=None):
        obj=self.get_object();qs=obj.attachments.filter(deleted_at__isnull=True).select_related("uploaded_by")
        if not self._internal(obj,"attachment"):qs=qs.filter(visibility=CollaborationVisibility.PUBLIC)
        if request.method=="GET":return Response(RequestAttachmentSerializer(qs,many=True).data)
        attachment=RequestCollaborationService.add_attachment(request=obj,actor=self.actor(),actor_user=request.user,uploaded_file=request.FILES.get("file"),visibility=request.data.get("visibility",CollaborationVisibility.PUBLIC));return Response(RequestAttachmentSerializer(attachment).data,status=201)
    @action(detail=True,methods=["delete"],url_path=r"attachments/(?P<attachment_id>[^/.]+)")
    def attachment_detail(self,request,pk=None,attachment_id=None):
        obj=self.get_object();qs=ServiceRequestAttachment.objects.filter(deleted_at__isnull=True)
        if not self._internal(obj,"attachment"):qs=qs.filter(visibility=CollaborationVisibility.PUBLIC)
        attachment=get_object_or_404(qs,pk=attachment_id,request=obj);RequestCollaborationService.delete_attachment(attachment=attachment,actor=self.actor(),actor_user=request.user);return Response(status=204)
    @action(detail=True,methods=["get"],url_path=r"attachments/(?P<attachment_id>[^/.]+)/download")
    def attachment_download(self,request,pk=None,attachment_id=None):
        obj=self.get_object();qs=ServiceRequestAttachment.objects.filter(deleted_at__isnull=True)
        if not self._internal(obj,"attachment"):qs=qs.filter(visibility=CollaborationVisibility.PUBLIC)
        attachment=get_object_or_404(qs,pk=attachment_id,request=obj);return FileResponse(attachment.file.open("rb"),as_attachment=True,filename=attachment.original_filename,content_type=attachment.content_type)
    @action(detail=True,methods=["post","delete"])
    def watch(self,request,pk=None):
        obj=self.get_object();actor=self.actor()
        if request.method=="POST":return Response(RequestWatcherSerializer(RequestCollaborationService.add_watcher(request=obj,employee=actor,actor=actor,actor_user=request.user)).data,status=201)
        RequestCollaborationService.remove_watcher(request=obj,employee=actor,actor=actor,actor_user=request.user);return Response(status=204)
    @action(detail=True,methods=["get","post"])
    def watchers(self,request,pk=None):
        obj=self.get_object()
        if request.method=="GET":return Response(RequestWatcherSerializer(obj.watcher_records.filter(removed_at__isnull=True,employee__is_active=True).select_related("employee","added_by"),many=True).data)
        s=RequestWatcherWriteSerializer(data=request.data);s.is_valid(raise_exception=True);watcher=RequestCollaborationService.add_watcher(request=obj,employee=s.validated_data["employee"],actor=self.actor(),actor_user=request.user);return Response(RequestWatcherSerializer(watcher).data,status=201)
    @action(detail=True,methods=["delete"],url_path=r"watchers/(?P<employee_id>[^/.]+)")
    def watcher_detail(self,request,pk=None,employee_id=None):
        obj=self.get_object();employee=get_object_or_404(Employee,pk=employee_id);RequestCollaborationService.remove_watcher(request=obj,employee=employee,actor=self.actor(),actor_user=request.user);return Response(status=204)
    @action(detail=True,methods=["get"])
    def activity(self,request,pk=None):
        return Response(ServiceRequestActivitySelector.page(request=self.get_object(),employee=self.actor(),page=request.query_params.get("page",1),page_size=request.query_params.get("page_size",25)))
