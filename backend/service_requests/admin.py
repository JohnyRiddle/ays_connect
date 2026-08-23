from django.contrib import admin
from .models import ServiceCategory, Service, RequestType, RequestTypeAccessRule, RequestFieldDefinition, RequestFieldOption, RequestTypeSchemaVersion

for model in (ServiceCategory,Service,RequestType,RequestTypeAccessRule,RequestFieldDefinition,RequestFieldOption,RequestTypeSchemaVersion):
    admin.site.register(model)
