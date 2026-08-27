import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class UUIDTimeModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta: abstract = True


class ServiceCategory(UUIDTimeModel):
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=64, null=True, blank=True, unique=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="children")
    position = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)
    class Meta:
        ordering = ["position", "name", "id"]
        constraints = [models.CheckConstraint(condition=~models.Q(id=models.F("parent_id")), name="service_category_parent_not_self")]
    def __str__(self): return self.name


class Service(UUIDTimeModel):
    category = models.ForeignKey(ServiceCategory, on_delete=models.PROTECT, related_name="services")
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=64, null=True, blank=True, unique=True)
    description = models.TextField(blank=True)
    owner_org_unit = models.ForeignKey("organizations.OrgUnit", on_delete=models.PROTECT, null=True, blank=True, related_name="owned_services")
    owner_functional_group = models.ForeignKey("employees.FunctionalGroup", on_delete=models.PROTECT, null=True, blank=True, related_name="owned_services")
    legal_entity = models.ForeignKey("organizations.LegalEntity", on_delete=models.PROTECT, null=True, blank=True, related_name="services")
    location = models.ForeignKey("organizations.Location", on_delete=models.PROTECT, null=True, blank=True, related_name="services")
    position = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)
    class Meta: ordering = ["position", "name", "id"]
    def __str__(self): return self.name


class RequestType(UUIDTimeModel):
    class Priority(models.TextChoices):
        LOW="low", "Low"; NORMAL="normal", "Normal"; HIGH="high", "High"; CRITICAL="critical", "Critical"
    class TaskCompletionPolicy(models.TextChoices):
        NONE="none", "No task restriction"; ALL_TERMINAL="all_execution_tasks_terminal", "All execution tasks terminal"; ALL_COMPLETED="all_execution_tasks_completed", "All execution tasks completed"
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="request_types")
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    instructions = models.TextField(blank=True)
    default_priority = models.CharField(max_length=16, choices=Priority.choices, default=Priority.NORMAL)
    position = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)
    allow_anonymous_employee = models.BooleanField(default=False)
    allow_self_service = models.BooleanField(default=True)
    task_completion_policy = models.CharField(max_length=40, choices=TaskCompletionPolicy.choices, default=TaskCompletionPolicy.NONE)
    created_by = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="created_request_types")
    current_schema_version = models.OneToOneField("RequestTypeSchemaVersion", on_delete=models.PROTECT, null=True, blank=True, related_name="current_for_type")
    class Meta: ordering = ["position", "name", "id"]
    def __str__(self): return self.name


class AccessScope(models.TextChoices):
    GLOBAL="global", "Global"; LEGAL_ENTITY="legal_entity", "Legal entity"; ORG_UNIT="org_unit", "Org unit"; LOCATION="location", "Location"; ROLE="role", "Role"


class RequestTypeAccessRule(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request_type = models.ForeignKey(RequestType, on_delete=models.CASCADE, related_name="access_rules")
    scope_type = models.CharField(max_length=24, choices=AccessScope.choices)
    legal_entity = models.ForeignKey("organizations.LegalEntity", on_delete=models.PROTECT, null=True, blank=True)
    org_unit = models.ForeignKey("organizations.OrgUnit", on_delete=models.PROTECT, null=True, blank=True)
    location = models.ForeignKey("organizations.Location", on_delete=models.PROTECT, null=True, blank=True)
    role = models.ForeignKey("access_control.Role", on_delete=models.PROTECT, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["created_at", "id"]
        constraints = [models.CheckConstraint(condition=(
            models.Q(scope_type="global",legal_entity__isnull=True,org_unit__isnull=True,location__isnull=True,role__isnull=True)
            | models.Q(scope_type="legal_entity",legal_entity__isnull=False,org_unit__isnull=True,location__isnull=True,role__isnull=True)
            | models.Q(scope_type="org_unit",legal_entity__isnull=True,org_unit__isnull=False,location__isnull=True,role__isnull=True)
            | models.Q(scope_type="location",legal_entity__isnull=True,org_unit__isnull=True,location__isnull=False,role__isnull=True)
            | models.Q(scope_type="role",legal_entity__isnull=True,org_unit__isnull=True,location__isnull=True,role__isnull=False)
        ),name="request_access_rule_exact_target")]


class FieldType(models.TextChoices):
    TEXT="text", "Text"; TEXTAREA="textarea", "Textarea"; INTEGER="integer", "Integer"; DECIMAL="decimal", "Decimal"; BOOLEAN="boolean", "Boolean"; DATE="date", "Date"; DATETIME="datetime", "Datetime"; CHOICE="choice", "Choice"; MULTI_CHOICE="multi_choice", "Multiple choice"; EMPLOYEE="employee", "Employee"; ORG_UNIT="org_unit", "Org unit"; LEGAL_ENTITY="legal_entity", "Legal entity"; LOCATION="location", "Location"; FILE="file", "File"


class RequestFieldDefinition(UUIDTimeModel):
    request_type = models.ForeignKey(RequestType, on_delete=models.CASCADE, related_name="fields")
    key = models.SlugField(max_length=100)
    label = models.CharField(max_length=200)
    help_text = models.TextField(blank=True)
    field_type = models.CharField(max_length=24, choices=FieldType.choices)
    required = models.BooleanField(default=False)
    position = models.PositiveIntegerField(default=0)
    default_value = models.JSONField(null=True, blank=True)
    config = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    class Meta:
        ordering = ["position", "key", "id"]
        constraints = [models.UniqueConstraint(fields=["request_type", "key"], name="unique_request_field_key")]
    def __str__(self): return f"{self.request_type.code}.{self.key}"


class RequestFieldOption(UUIDTimeModel):
    field = models.ForeignKey(RequestFieldDefinition, on_delete=models.CASCADE, related_name="options")
    value = models.CharField(max_length=100)
    label = models.CharField(max_length=200)
    position = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)
    class Meta:
        ordering = ["position", "value", "id"]
        constraints = [models.UniqueConstraint(fields=["field", "value"], name="unique_request_field_option")]


class RequestTypeSchemaVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request_type = models.ForeignKey(RequestType, on_delete=models.PROTECT, related_name="schema_versions")
    version = models.PositiveIntegerField()
    schema_json = models.JSONField()
    created_by = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="published_request_schemas")
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["-version"]
        constraints = [models.UniqueConstraint(fields=["request_type", "version"], name="unique_request_schema_version")]
    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists(): raise ValidationError("Published schema versions are immutable.")
        return super().save(*args, **kwargs)
    def delete(self, *args, **kwargs): raise ValidationError("Published schema versions are immutable.")


class RequestStatus(models.TextChoices):
    NEW="new", "New"; ASSIGNED="assigned", "Assigned"; IN_PROGRESS="in_progress", "In progress"
    WAITING_REQUESTER="waiting_requester", "Waiting requester"; WAITING_EXTERNAL="waiting_external", "Waiting external"
    RESOLVED="resolved", "Resolved"; CLOSED="closed", "Closed"; CANCELLED="cancelled", "Cancelled"


class RequestNumberSequence(models.Model):
    key = models.CharField(max_length=32, primary_key=True, default="request")
    value = models.PositiveBigIntegerField(default=0)


class ServiceRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    number = models.CharField(max_length=32, unique=True, editable=False)
    request_type = models.ForeignKey(RequestType, on_delete=models.PROTECT, related_name="requests")
    schema_version = models.ForeignKey(RequestTypeSchemaVersion, on_delete=models.PROTECT, related_name="requests")
    requester = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="service_requests")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_service_requests")
    subject = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    priority = models.CharField(max_length=16, choices=RequestType.Priority.choices, default=RequestType.Priority.NORMAL, db_index=True)
    status = models.CharField(max_length=24, choices=RequestStatus.choices, default=RequestStatus.NEW, db_index=True)
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="requests")
    category = models.ForeignKey(ServiceCategory, on_delete=models.PROTECT, related_name="requests")
    responsible_target = models.ForeignKey("employees.AssignmentTarget", on_delete=models.PROTECT, null=True, blank=True, related_name="responsible_requests")
    responsible_employee = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, null=True, blank=True, related_name="responsible_requests")
    assigned_target = models.ForeignKey("employees.AssignmentTarget", on_delete=models.PROTECT, null=True, blank=True, related_name="assigned_requests")
    assigned_employee = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, null=True, blank=True, related_name="assigned_requests")
    org_unit = models.ForeignKey("organizations.OrgUnit", on_delete=models.PROTECT, null=True, blank=True, related_name="service_requests")
    legal_entity = models.ForeignKey("organizations.LegalEntity", on_delete=models.PROTECT, null=True, blank=True, related_name="service_requests")
    location = models.ForeignKey("organizations.Location", on_delete=models.PROTECT, null=True, blank=True, related_name="service_requests")
    routing_unresolved = models.BooleanField(default=False, db_index=True)
    submitted_at = models.DateTimeField(null=True, blank=True); assigned_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True); resolved_at = models.DateTimeField(null=True, blank=True, db_index=True)
    closed_at = models.DateTimeField(null=True, blank=True, db_index=True); cancelled_at = models.DateTimeField(null=True, blank=True)
    reopened_at = models.DateTimeField(null=True, blank=True)
    resolution_code = models.CharField(max_length=64, blank=True); resolution_comment = models.TextField(blank=True)
    cancellation_reason = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="updated_service_requests")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    class Meta:
        ordering=("-created_at",)
        indexes=[models.Index(fields=["request_type"]),models.Index(fields=["service"]),models.Index(fields=["requester"]),models.Index(fields=["assigned_employee"]),models.Index(fields=["responsible_employee"]),models.Index(fields=["org_unit"]),models.Index(fields=["legal_entity"]),models.Index(fields=["location"]),models.Index(fields=["status","created_at"])]
    def delete(self,*args,**kwargs): raise TypeError("Production ServiceRequest cannot be hard deleted")
    def save(self,*args,**kwargs):
        if self.pk:
            old=type(self).objects.filter(pk=self.pk).values_list("number",flat=True).first()
            if old is not None and old != self.number: raise TypeError("Request number is immutable")
        return super().save(*args,**kwargs)


class RequestRoutingRule(UUIDTimeModel):
    request_type=models.ForeignKey(RequestType,on_delete=models.CASCADE,related_name="routing_rules")
    order=models.PositiveIntegerField(default=100)
    target=models.ForeignKey("employees.AssignmentTarget",on_delete=models.PROTECT,related_name="request_routing_rules")
    legal_entity=models.ForeignKey("organizations.LegalEntity",on_delete=models.PROTECT,null=True,blank=True)
    org_unit=models.ForeignKey("organizations.OrgUnit",on_delete=models.PROTECT,null=True,blank=True)
    location=models.ForeignKey("organizations.Location",on_delete=models.PROTECT,null=True,blank=True)
    priority=models.CharField(max_length=16,choices=RequestType.Priority.choices,blank=True)
    is_active=models.BooleanField(default=True,db_index=True)
    class Meta: ordering=("order","id")


class ServiceRequestFieldValue(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    request=models.ForeignKey(ServiceRequest,on_delete=models.PROTECT,related_name="field_values")
    field_key=models.CharField(max_length=100); field_type=models.CharField(max_length=24,choices=FieldType.choices)
    label=models.CharField(max_length=200); value_json=models.JSONField(null=True)
    created_at=models.DateTimeField(auto_now_add=True); updated_at=models.DateTimeField(auto_now=True)
    class Meta: constraints=[models.UniqueConstraint(fields=["request","field_key"],name="unique_request_field_value")]


class ServiceRequestFieldRevision(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    request=models.ForeignKey(ServiceRequest,on_delete=models.PROTECT,related_name="field_revisions")
    old_values=models.JSONField(default=dict); new_values=models.JSONField(default=dict)
    changed_by=models.ForeignKey("employees.Employee",on_delete=models.PROTECT,related_name="request_field_revisions")
    created_at=models.DateTimeField(auto_now_add=True)


class ServiceRequestStatusHistory(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    request=models.ForeignKey(ServiceRequest,on_delete=models.PROTECT,related_name="status_history")
    from_status=models.CharField(max_length=24,choices=RequestStatus.choices,blank=True); to_status=models.CharField(max_length=24,choices=RequestStatus.choices)
    actor=models.ForeignKey("employees.Employee",on_delete=models.PROTECT,related_name="request_status_changes")
    reason=models.TextField(blank=True); created_at=models.DateTimeField(auto_now_add=True)
    class Meta: ordering=("created_at",)


class ServiceRequestAssignmentHistory(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    request=models.ForeignKey(ServiceRequest,on_delete=models.PROTECT,related_name="assignment_history")
    old_target=models.ForeignKey("employees.AssignmentTarget",on_delete=models.PROTECT,null=True,blank=True,related_name="old_request_assignments")
    old_employee=models.ForeignKey("employees.Employee",on_delete=models.PROTECT,null=True,blank=True,related_name="old_request_assignments")
    new_target=models.ForeignKey("employees.AssignmentTarget",on_delete=models.PROTECT,related_name="new_request_assignments")
    new_employee=models.ForeignKey("employees.Employee",on_delete=models.PROTECT,related_name="new_request_assignments")
    changed_by=models.ForeignKey("employees.Employee",on_delete=models.PROTECT,related_name="request_assignment_changes")
    reason=models.TextField(blank=True); created_at=models.DateTimeField(auto_now_add=True)


class ServiceRequestWaitingPeriod(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    request=models.ForeignKey(ServiceRequest,on_delete=models.PROTECT,related_name="waiting_periods")
    waiting_type=models.CharField(max_length=24,choices=[(RequestStatus.WAITING_REQUESTER,"Requester"),(RequestStatus.WAITING_EXTERNAL,"External")])
    comment=models.TextField(); started_at=models.DateTimeField(auto_now_add=True); ended_at=models.DateTimeField(null=True,blank=True)
    started_by=models.ForeignKey("employees.Employee",on_delete=models.PROTECT,related_name="started_request_waits")
    ended_by=models.ForeignKey("employees.Employee",on_delete=models.PROTECT,null=True,blank=True,related_name="ended_request_waits")
    class Meta: constraints=[models.UniqueConstraint(fields=["request"],condition=models.Q(ended_at__isnull=True),name="one_active_wait_per_request")]


class ServiceRequestRelation(models.Model):
    class Type(models.TextChoices): DUPLICATE_OF="duplicate_of","Duplicate of"; RELATED_TO="related_to","Related to"
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    from_request=models.ForeignKey(ServiceRequest,on_delete=models.PROTECT,related_name="outgoing_relations")
    to_request=models.ForeignKey(ServiceRequest,on_delete=models.PROTECT,related_name="incoming_relations")
    relation_type=models.CharField(max_length=20,choices=Type.choices); created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["from_request","to_request","relation_type"],name="unique_request_relation"),models.CheckConstraint(condition=~models.Q(from_request=models.F("to_request")),name="request_relation_not_self")]


class ServiceRequestTask(models.Model):
    class Type(models.TextChoices): EXECUTION="execution","Execution"; FOLLOW_UP="follow_up","Follow-up"
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    request=models.ForeignKey(ServiceRequest,on_delete=models.PROTECT,related_name="task_links")
    task=models.ForeignKey("work_tasks.Task",on_delete=models.PROTECT,related_name="request_links")
    relation_type=models.CharField(max_length=20,choices=Type.choices,default=Type.EXECUTION)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="created_request_task_links")
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta: constraints=[models.UniqueConstraint(fields=["request","task"],name="unique_request_task_link")]


class CollaborationVisibility(models.TextChoices):
    PUBLIC="public","Public"; INTERNAL="internal","Internal"


class ServiceRequestComment(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    request=models.ForeignKey(ServiceRequest,on_delete=models.PROTECT,related_name="comments")
    author=models.ForeignKey("employees.Employee",on_delete=models.PROTECT,related_name="request_comments")
    body=models.TextField();visibility=models.CharField(max_length=16,choices=CollaborationVisibility.choices,default=CollaborationVisibility.PUBLIC,db_index=True)
    created_at=models.DateTimeField(auto_now_add=True);updated_at=models.DateTimeField(auto_now=True);edited_at=models.DateTimeField(null=True,blank=True)
    deleted_at=models.DateTimeField(null=True,blank=True);deleted_by=models.ForeignKey("employees.Employee",on_delete=models.PROTECT,null=True,blank=True,related_name="deleted_request_comments")
    class Meta:ordering=("created_at","id");indexes=[models.Index(fields=["request","visibility","created_at"])]


class ServiceRequestCommentRevision(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    comment=models.ForeignKey(ServiceRequestComment,on_delete=models.PROTECT,related_name="revisions")
    body=models.TextField();edited_by=models.ForeignKey("employees.Employee",on_delete=models.PROTECT,related_name="request_comment_revisions")
    created_at=models.DateTimeField(auto_now_add=True)


class ServiceRequestCommentMention(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    comment=models.ForeignKey(ServiceRequestComment,on_delete=models.PROTECT,related_name="mention_records")
    employee=models.ForeignKey("employees.Employee",on_delete=models.PROTECT,related_name="request_comment_mentions")
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:constraints=[models.UniqueConstraint(fields=["comment","employee"],name="unique_request_comment_mention")]


def request_attachment_path(instance,filename):return f"requests/{instance.request_id}/{instance.pk}/file"


class ServiceRequestAttachment(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    request=models.ForeignKey(ServiceRequest,on_delete=models.PROTECT,related_name="attachments")
    file=models.FileField(upload_to=request_attachment_path,max_length=500)
    original_filename=models.CharField(max_length=255);content_type=models.CharField(max_length=120);size=models.PositiveBigIntegerField();checksum=models.CharField(max_length=64,db_index=True)
    uploaded_by=models.ForeignKey("employees.Employee",on_delete=models.PROTECT,related_name="uploaded_request_attachments")
    visibility=models.CharField(max_length=16,choices=CollaborationVisibility.choices,default=CollaborationVisibility.PUBLIC,db_index=True)
    created_at=models.DateTimeField(auto_now_add=True);deleted_at=models.DateTimeField(null=True,blank=True);deleted_by=models.ForeignKey("employees.Employee",on_delete=models.PROTECT,null=True,blank=True,related_name="deleted_request_attachments")
    class Meta:ordering=("created_at","id");indexes=[models.Index(fields=["request","visibility","created_at"])]


class ServiceRequestWatcher(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    request=models.ForeignKey(ServiceRequest,on_delete=models.PROTECT,related_name="watcher_records")
    employee=models.ForeignKey("employees.Employee",on_delete=models.PROTECT,related_name="watched_service_requests")
    added_by=models.ForeignKey("employees.Employee",on_delete=models.PROTECT,related_name="added_request_watchers")
    created_at=models.DateTimeField(auto_now_add=True);removed_at=models.DateTimeField(null=True,blank=True);removed_by=models.ForeignKey("employees.Employee",on_delete=models.PROTECT,null=True,blank=True,related_name="removed_request_watchers")
    class Meta:
        constraints=[models.UniqueConstraint(fields=["request","employee"],condition=models.Q(removed_at__isnull=True),name="unique_active_request_watcher")]
        indexes=[models.Index(fields=["request","employee","removed_at"])]
