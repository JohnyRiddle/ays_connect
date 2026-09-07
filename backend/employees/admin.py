from django.contrib import admin
from .models import AssignmentTarget, Employee, EmployeeDataChangeRequest, EmployeeFacility, EmployeeInvitation, EmployeeProfile, FirstLoginProgress, FunctionalGroup, FunctionalGroupMembership, OnboardingInstance, OnboardingStepInstance, OnboardingTemplate, OnboardingTemplateStep, OnboardingTemplateVersion, Position, Team, TeamMembership
admin.site.register(Employee)
admin.site.register(EmployeeFacility)
admin.site.register(Position)
admin.site.register(FunctionalGroup)
admin.site.register(FunctionalGroupMembership)
admin.site.register(AssignmentTarget)


class ImmutableHistoryAdmin(admin.ModelAdmin):
    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False


@admin.register(EmployeeInvitation)
class EmployeeInvitationAdmin(ImmutableHistoryAdmin):
    list_display=("employee","delivery_address","status","expires_at","sent_at","used_at")
    list_filter=("status","created_at","expires_at")
    search_fields=("employee__employee_number","employee__first_name","employee__last_name","delivery_address")
    readonly_fields=("employee","delivery_address","status","created_by","created_at","expires_at","used_at","revoked_at","sent_at","accepted_by","revoke_reason","version")


@admin.register(OnboardingTemplate)
class OnboardingTemplateAdmin(admin.ModelAdmin):
    list_display=("name","status","scope","published_version","updated_at")
    list_filter=("status","scope")
    search_fields=("name",)
    def has_delete_permission(self,request,obj=None):return False


@admin.register(OnboardingTemplateVersion)
class OnboardingTemplateVersionAdmin(ImmutableHistoryAdmin):
    list_display=("template","number","published_at","published_by")
    readonly_fields=("template","number","name_snapshot","description_snapshot","published_at","published_by")


@admin.register(OnboardingTemplateStep)
class OnboardingTemplateStepAdmin(ImmutableHistoryAdmin):
    list_display=("title","version","step_type","position","required")
    list_filter=("step_type","required")
    readonly_fields=tuple(field.name for field in OnboardingTemplateStep._meta.fields)


@admin.register(OnboardingInstance)
class OnboardingInstanceAdmin(ImmutableHistoryAdmin):
    list_display=("employee","status","template_version","progress_percent","created_at")
    list_filter=("status","created_at")
    search_fields=("employee__employee_number","employee__first_name","employee__last_name")
    readonly_fields=tuple(field.name for field in OnboardingInstance._meta.fields)
    list_select_related=("employee","template_version")


@admin.register(OnboardingStepInstance)
class OnboardingStepInstanceAdmin(ImmutableHistoryAdmin):
    list_display=("title_snapshot","onboarding","status","responsible_employee","due_at")
    list_filter=("status","due_at")
    readonly_fields=tuple(field.name for field in OnboardingStepInstance._meta.fields)
    list_select_related=("onboarding","responsible_employee")

admin.site.register(FirstLoginProgress)

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

@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(admin.ModelAdmin):
    list_display=("employee","preferred_name","timezone","version","updated_at")
    search_fields=("employee__employee_number","employee__last_name","preferred_name")
    readonly_fields=("employee","preferred_name","bio","additional_email","additional_phone","timezone","preferred_language","bio_visibility","additional_email_visibility","additional_phone_visibility","version","created_at","updated_at")
    def has_add_permission(self,request):return False
    def has_delete_permission(self,request,obj=None):return False

@admin.register(EmployeeDataChangeRequest)
class EmployeeDataChangeRequestAdmin(admin.ModelAdmin):
    list_display=("id","employee","field_type","status","submitted_at","reviewed_by","applied_at")
    list_filter=("field_type","status")
    search_fields=("employee__employee_number","employee__last_name")
    readonly_fields=tuple(field.name for field in EmployeeDataChangeRequest._meta.fields)
    def has_add_permission(self,request):return False
    def has_delete_permission(self,request,obj=None):return False
