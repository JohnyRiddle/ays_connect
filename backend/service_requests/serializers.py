from rest_framework import serializers
from employees.models import Employee
from .models import (ServiceCategory, Service, RequestType, RequestTypeAccessRule, RequestFieldDefinition, RequestFieldOption, RequestTypeSchemaVersion,
 ServiceRequest, ServiceRequestFieldValue, RequestRoutingRule, ServiceRequestTask, ServiceRequestComment, ServiceRequestAttachment, ServiceRequestWatcher, CollaborationVisibility, RequestStatus)


class CategorySerializer(serializers.ModelSerializer):
    class Meta: model=ServiceCategory; fields="__all__"; read_only_fields=("id","created_at","updated_at")
class ServiceSerializer(serializers.ModelSerializer):
    class Meta: model=Service; fields="__all__"; read_only_fields=("id","created_at","updated_at")
class AccessRuleSerializer(serializers.ModelSerializer):
    class Meta: model=RequestTypeAccessRule; fields="__all__"; read_only_fields=("id","created_at","request_type")
    def validate(self,data):
        scope=data.get("scope_type"); mapping={"legal_entity":"legal_entity","org_unit":"org_unit","location":"location","role":"role"}
        populated=[name for name in ("legal_entity","org_unit","location","role") if data.get(name)]
        expected=mapping.get(scope)
        if scope=="global" and populated: raise serializers.ValidationError("GLOBAL rule cannot have a target.")
        if expected and populated!=[expected]: raise serializers.ValidationError(f"{scope} rule requires only {expected}.")
        return data
class OptionSerializer(serializers.ModelSerializer):
    class Meta: model=RequestFieldOption; fields="__all__"; read_only_fields=("id","created_at","updated_at","field")
class FieldSerializer(serializers.ModelSerializer):
    options=OptionSerializer(many=True,read_only=True)
    class Meta: model=RequestFieldDefinition; fields="__all__"; read_only_fields=("id","created_at","updated_at","request_type")
class SchemaVersionSerializer(serializers.ModelSerializer):
    class Meta: model=RequestTypeSchemaVersion; fields="__all__"; read_only_fields=("id","request_type","version","schema_json","created_by","created_at")
class RequestTypeSerializer(serializers.ModelSerializer):
    current_schema_version_number=serializers.IntegerField(source="current_schema_version.version",read_only=True)
    class Meta:
        model=RequestType; fields="__all__"
        read_only_fields=("id","created_at","updated_at","created_by","current_schema_version")

class RoutingRuleSerializer(serializers.ModelSerializer):
    class Meta:model=RequestRoutingRule;fields="__all__";read_only_fields=("id","request_type","created_at","updated_at")

class RequestFieldValueSerializer(serializers.ModelSerializer):
    value=serializers.JSONField(source="value_json")
    type=serializers.CharField(source="field_type")
    key=serializers.CharField(source="field_key")
    class Meta:model=ServiceRequestFieldValue;fields=("id","key","type","label","value");read_only_fields=fields

class RequestTaskLinkSerializer(serializers.ModelSerializer):
    number=serializers.CharField(source="task.number",read_only=True);title=serializers.CharField(source="task.title",read_only=True);status=serializers.CharField(source="task.status",read_only=True)
    class Meta:model=ServiceRequestTask;fields=("id","task","relation_type","number","title","status","created_at");read_only_fields=fields

class ServiceRequestSerializer(serializers.ModelSerializer):
    dynamic_values=RequestFieldValueSerializer(source="field_values",many=True,read_only=True)
    tasks=RequestTaskLinkSerializer(source="task_links",many=True,read_only=True)
    available_actions=serializers.SerializerMethodField()
    collaboration=serializers.SerializerMethodField();tasks_summary=serializers.SerializerMethodField();sla=serializers.SerializerMethodField();escalation=serializers.SerializerMethodField()
    request_type_name=serializers.CharField(source="request_type.name",read_only=True)
    schema_version_number=serializers.IntegerField(source="schema_version.version",read_only=True)
    class Meta:
        model=ServiceRequest;fields="__all__"
        read_only_fields=("id","number","status","requester","created_by","service","category","schema_version","responsible_target","responsible_employee","assigned_target","assigned_employee","submitted_at","assigned_at","started_at","resolved_at","closed_at","cancelled_at","reopened_at","resolution_code","resolution_comment","cancellation_reason","version","created_at","updated_at","updated_by","routing_unresolved")
    def get_available_actions(self,obj):
        from .state_machine import ServiceRequestStateMachine
        from .policies import ServiceRequestAccessPolicy
        req=self.context.get("request");employee=getattr(getattr(req,"user",None),"employee",None);superuser=bool(req and req.user.is_superuser)
        candidates={"assign":"request.assign","reassign":"request.reassign","start":"request.start","wait_requester":"request.wait","wait_external":"request.wait","resume":"request.start","resolve":"request.resolve","close":"request.close","reopen":"request.reopen","cancel":"request.cancel","task_create":"request.task_create","comment":"request.comment","comment_internal":"request.comment_internal","attachment_add":"request.attachment_add","attachment_internal":"request.attachment_internal","watch":"request.watch","watcher_manage":"request.watcher_manage"}
        state=set()
        if obj.status==RequestStatus.NEW:state|={"assign","cancel"}
        if obj.status==RequestStatus.ASSIGNED:state|={"reassign","start","cancel"}
        if obj.status==RequestStatus.IN_PROGRESS:state|={"reassign","wait_requester","wait_external","resolve","cancel"}
        if obj.status in {RequestStatus.WAITING_REQUESTER,RequestStatus.WAITING_EXTERNAL}:state|={"reassign","resume","cancel"}
        if obj.status==RequestStatus.RESOLVED:state|={"reassign","close","reopen"}
        if obj.status==RequestStatus.CLOSED:state|={"reopen"}
        if obj.status!=RequestStatus.CANCELLED:state|={"comment","comment_internal","watch","watcher_manage","task_create"}
        if obj.status not in {RequestStatus.CLOSED,RequestStatus.CANCELLED}:state|={"attachment_add","attachment_internal"}
        if any(link.employee_id==getattr(employee,"pk",None) and not link.removed_at for link in obj.watcher_records.all()):state.discard("watch");state.add("unwatch")
        return sorted(action for action in state if action=="unwatch" or superuser or ServiceRequestAccessPolicy.allows(employee=employee,permission=candidates[action],request=obj))
    def get_collaboration(self,obj):
        from .policies import ServiceRequestAccessPolicy
        req=self.context.get("request");employee=getattr(getattr(req,"user",None),"employee",None);superuser=bool(req and req.user.is_superuser);comment_internal=superuser or ServiceRequestAccessPolicy.can_view_internal(employee=employee,request=obj,kind="comment");attachment_internal=superuser or ServiceRequestAccessPolicy.can_view_internal(employee=employee,request=obj,kind="attachment")
        comments=list(obj.comments.all());attachments=list(obj.attachments.all());watchers=list(obj.watcher_records.all());links=list(obj.task_links.all())
        data={"public_comments_count":sum(not x.deleted_at and x.visibility=="public" for x in comments),"attachments_count":sum(not x.deleted_at and x.visibility=="public" for x in attachments),"watchers_count":sum(not x.removed_at and x.employee.is_active for x in watchers),"tasks_count":len(links)}
        if comment_internal:data["internal_comments_count"]=sum(not x.deleted_at and x.visibility=="internal" for x in comments)
        if attachment_internal:data["attachments_count"]=sum(not x.deleted_at for x in attachments)
        return data
    def get_tasks_summary(self,obj):
        statuses=[link.task.status for link in obj.task_links.all()];return {"total":len(statuses),"open":statuses.count("open"),"in_progress":statuses.count("in_progress"),"completed":statuses.count("completed")}
    def get_sla(self,obj):
        try:instance=obj.sla_instance
        except Exception:return {"has_sla":False}
        metrics=list(instance.metrics.all());response=next((x for x in metrics if x.metric_type=="response"),None);resolution=next((x for x in reversed(metrics) if x.metric_type=="resolution"),None)
        return {"has_sla":True,"response_status":response.status if response else None,"resolution_status":resolution.status if resolution else None,"resolution_due_at":resolution.due_at if resolution else None,"is_paused":instance.status=="paused"}
    def get_escalation(self,obj):
        try:instance=obj.sla_instance.escalation_instance
        except Exception:return {"has_escalation":False}
        executions=list(instance.executions.all());return {"has_escalation":True,"current_level":max((x.rule_snapshot.get("level",0) for x in executions if x.status in {"succeeded","skipped"}),default=0),"last_triggered_at":max((x.triggered_at for x in executions),default=None),"has_failed_actions":any(x.status=="failed" for x in executions)}

class RequestCreateSerializer(serializers.Serializer):
    request_type=serializers.PrimaryKeyRelatedField(queryset=RequestType.objects.all());requester=serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all(),required=False)
    subject=serializers.CharField(max_length=240);description=serializers.CharField(required=False,allow_blank=True);priority=serializers.ChoiceField(choices=RequestType.Priority.choices,required=False);payload=serializers.JSONField()

class RequestCommentSerializer(serializers.ModelSerializer):
    body=serializers.SerializerMethodField();mentions=serializers.SerializerMethodField()
    class Meta:model=ServiceRequestComment;fields=("id","author","body","visibility","mentions","created_at","updated_at","edited_at","deleted_at","deleted_by");read_only_fields=fields
    def get_body(self,obj):return "Комментарий удалён" if obj.deleted_at else obj.body
    def get_mentions(self,obj):return [str(pk) for pk in obj.mention_records.values_list("employee_id",flat=True)]
class RequestCommentWriteSerializer(serializers.Serializer):
    body=serializers.CharField();visibility=serializers.ChoiceField(choices=CollaborationVisibility.choices,default=CollaborationVisibility.PUBLIC,required=False);mentions=serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all(),many=True,required=False)
class RequestAttachmentSerializer(serializers.ModelSerializer):
    class Meta:model=ServiceRequestAttachment;fields=("id","original_filename","content_type","size","checksum","uploaded_by","visibility","created_at","deleted_at","deleted_by");read_only_fields=fields
class RequestWatcherSerializer(serializers.ModelSerializer):
    class Meta:model=ServiceRequestWatcher;fields=("id","employee","added_by","created_at","removed_at","removed_by");read_only_fields=fields
class RequestWatcherWriteSerializer(serializers.Serializer):employee=serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all())
