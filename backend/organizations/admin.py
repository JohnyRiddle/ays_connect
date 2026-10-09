from django.contrib import admin
from .models import Cluster, Company, Department, Facility, LegalEntity, Location, OrgUnit, Region, Zone
for model in (Company, Region, Cluster, Facility, Department, Zone, LegalEntity): admin.site.register(model)

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "node_kind", "business_status", "is_archived")
    readonly_fields = tuple(field.name for field in Location._meta.fields)
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
    def get_fields(self, request, obj=None):
        from rest_framework.exceptions import NotFound
        from .object_services import ObjectService
        fields = list(super().get_fields(request, obj))
        if obj:
            for field in ("parent", "legal_entity", "org_unit"):
                value = getattr(obj, field)
                if value:
                    try:
                        ObjectService.relation(request.user, value, value.__class__)
                    except NotFound:
                        fields.remove(field)
        return fields
    def get_queryset(self, request):
        from .object_policies import LocationAccessPolicy
        return LocationAccessPolicy.visible(request.user)

@admin.register(OrgUnit)
class OrgUnitAdmin(admin.ModelAdmin):
    list_display=("code","name","unit_type","status","legal_entity","parent")
    list_filter=("unit_type","status","legal_entity")
    search_fields=("code","name","short_name")
    readonly_fields=("id","parent","status","valid_from","valid_to","is_active","created_at","updated_at","version")
    def has_delete_permission(self,request,obj=None): return False
