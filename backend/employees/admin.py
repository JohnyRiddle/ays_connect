from django.contrib import admin
from .models import AssignmentTarget, Employee, EmployeeFacility, FunctionalGroup, FunctionalGroupMembership, Position, Team, TeamMembership
admin.site.register(Employee)
admin.site.register(EmployeeFacility)
admin.site.register(Position)
admin.site.register(FunctionalGroup)
admin.site.register(FunctionalGroupMembership)
admin.site.register(AssignmentTarget)

class TeamMembershipInline(admin.TabularInline):
    model=TeamMembership; extra=0; can_delete=False
    readonly_fields=("employee","role","membership_type","valid_from","valid_to","allocation_percent","is_primary_in_team","created_by","ended_by","end_reason","version")
    def has_add_permission(self,request,obj=None): return False

@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display=("code","name","team_type","status","legal_entity","org_unit","lead_employee")
    list_filter=("team_type","status","legal_entity","org_unit")
    search_fields=("code","name","short_name")
    readonly_fields=("id","code","status","parent_team","owner_employee","lead_employee","valid_from","valid_to","is_assignable","version","created_at","updated_at","created_by","updated_by")
    inlines=(TeamMembershipInline,)
    def has_delete_permission(self,request,obj=None): return False
    def has_add_permission(self,request): return False

@admin.register(TeamMembership)
class TeamMembershipAdmin(admin.ModelAdmin):
    list_display=("team","employee","role","membership_type","valid_from","valid_to")
    list_filter=("role","membership_type","team__status")
    search_fields=("team__code","team__name","employee__employee_number","employee__last_name")
    readonly_fields=("id","team","employee","role","membership_type","valid_from","valid_to","allocation_percent","is_primary_in_team","created_at","updated_at","created_by","ended_by","end_reason","version")
    def has_add_permission(self,request): return False
    def has_delete_permission(self,request,obj=None): return False
