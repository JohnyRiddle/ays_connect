from django.contrib import admin
from .models import Cluster, Company, Department, Facility, LegalEntity, Location, OrgUnit, Region, Zone
for model in (Company, Region, Cluster, Facility, Department, Zone, LegalEntity, Location): admin.site.register(model)

@admin.register(OrgUnit)
class OrgUnitAdmin(admin.ModelAdmin):
    list_display=("code","name","unit_type","status","legal_entity","parent")
    list_filter=("unit_type","status","legal_entity")
    search_fields=("code","name","short_name")
    readonly_fields=("id","parent","status","valid_from","valid_to","is_active","created_at","updated_at","version")
    def has_delete_permission(self,request,obj=None): return False
