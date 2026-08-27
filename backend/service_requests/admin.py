from django.contrib import admin
from .models import (ServiceCategory, Service, RequestType, RequestTypeAccessRule, RequestFieldDefinition, RequestFieldOption, RequestTypeSchemaVersion,
 ServiceRequest, ServiceRequestFieldValue, RequestRoutingRule, ServiceRequestAssignmentHistory, ServiceRequestStatusHistory, ServiceRequestWaitingPeriod, ServiceRequestTask,
 ServiceRequestComment,ServiceRequestCommentRevision,ServiceRequestCommentMention,ServiceRequestAttachment,ServiceRequestWatcher)

for model in (ServiceCategory,Service,RequestType,RequestTypeAccessRule,RequestFieldDefinition,RequestFieldOption,RequestTypeSchemaVersion):
    admin.site.register(model)

@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    list_display=("number","subject","status","priority","requester","assigned_employee","created_at")
    list_filter=("status","priority","request_type","service");search_fields=("number","subject","description")
    readonly_fields=("number","status","requester","created_by","schema_version","service","category","responsible_target","responsible_employee","assigned_target","assigned_employee","submitted_at","assigned_at","started_at","resolved_at","closed_at","cancelled_at","reopened_at","resolution_code","resolution_comment","cancellation_reason","version","created_at","updated_at","updated_by")

for model in (ServiceRequestFieldValue,RequestRoutingRule,ServiceRequestAssignmentHistory,ServiceRequestStatusHistory,ServiceRequestWaitingPeriod,ServiceRequestTask):admin.site.register(model)

@admin.register(ServiceRequestComment)
class RequestCommentAdmin(admin.ModelAdmin):
    list_display=("request","author","visibility","created_at","deleted_at");list_filter=("visibility","deleted_at")
    readonly_fields=("request","author","visibility","created_at","updated_at","edited_at","deleted_at","deleted_by")
@admin.register(ServiceRequestAttachment)
class RequestAttachmentAdmin(admin.ModelAdmin):
    list_display=("request","original_filename","visibility","uploaded_by","created_at","deleted_at");readonly_fields=("request","uploaded_by","visibility","original_filename","content_type","size","checksum","created_at","deleted_at","deleted_by","file")
for model in (ServiceRequestCommentRevision,ServiceRequestCommentMention,ServiceRequestWatcher):admin.site.register(model)
