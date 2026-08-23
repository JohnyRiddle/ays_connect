from django.db import transaction
from django.db.models import Prefetch
from django.db.models import Q
from django.utils import timezone
from access_control.models import EmployeeRole
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from audit.services import AuditService
from events.services import DomainEventService
from .models import ServiceCategory, Service, RequestType, RequestTypeAccessRule, RequestFieldDefinition, RequestFieldOption
from .serializers import CategorySerializer, ServiceSerializer, RequestTypeSerializer, AccessRuleSerializer, FieldSerializer, OptionSerializer, SchemaVersionSerializer
from .services import CategoryService, RequestTypeAccessPolicy, SchemaService, require, CatalogError


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
