from rest_framework.routers import DefaultRouter
from employees.internal_api import AssignmentTargetViewSet, EmployeeViewSet, FunctionalGroupViewSet, PositionViewSet
from employees.teams_api import TeamViewSet
from employees.onboarding_api import EmployeeDirectoryViewSet, RegistrationViewSet
from organizations.internal_api import LegalEntityViewSet, LocationViewSet, OrgUnitViewSet
from .views import PermissionViewSet, RolePermissionViewSet, RoleViewSet
from work_tasks.views import ChecklistTemplateViewSet, ProductionTaskViewSet
from work_tasks.automation_views import OccurrenceViewSet, RecurrenceViewSet, SavedViewViewSet, TaskTemplateViewSet
from service_requests.views import CategoryViewSet, ServiceViewSet, RequestTypeViewSet, ServiceCatalogView, ServiceRequestViewSet
from django.urls import path
from sla.views import CalendarViewSet, PolicyViewSet, AssignmentRuleViewSet, PreviewViewSet, EscalationPolicyViewSet, EscalationPolicyVersionViewSet, EscalationBindingViewSet
from employees.profile_api import AvatarView, ChangeRequestReviewViewSet, CompletenessView, DirectoryViewSet, MeView, OrganizationView, SelfChangeRequestViewSet, TeamsView, VisibilityView
from employees.onboarding_phase24_api import AccountAccessView, AccountBlockView, AccountReactivateView, AccountRestoreView, FirstLoginView, InvitationViewSet, OnboardingTemplateViewSet, OnboardingViewSet, SelfOnboardingViewSet

router = DefaultRouter()
router.register("employees", EmployeeViewSet, basename="internal-employees")
router.register("people/employees", EmployeeDirectoryViewSet, basename="people-employees")
router.register("people/registrations", RegistrationViewSet, basename="people-registrations")
router.register("people/directory", DirectoryViewSet, basename="people-directory")
router.register("people/change-requests", ChangeRequestReviewViewSet, basename="people-change-requests")
router.register("people/invitations", InvitationViewSet, basename="people-invitations")
router.register("people/onboarding", OnboardingViewSet, basename="people-onboarding")
router.register("people/onboarding-templates", OnboardingTemplateViewSet, basename="people-onboarding-templates")
router.register("people/me/onboarding", SelfOnboardingViewSet, basename="people-self-onboarding")
router.register("positions", PositionViewSet, basename="internal-positions")
router.register("legal-entities", LegalEntityViewSet, basename="internal-legal-entities")
router.register("org-units", OrgUnitViewSet, basename="internal-org-units")
router.register("locations", LocationViewSet, basename="internal-locations")
router.register("functional-groups", FunctionalGroupViewSet, basename="internal-functional-groups")
router.register("teams", TeamViewSet, basename="internal-teams")
router.register("assignment-targets", AssignmentTargetViewSet, basename="internal-assignment-targets")
router.register("roles", RoleViewSet, basename="internal-roles")
router.register("permissions", PermissionViewSet, basename="internal-permissions")
router.register("role-permissions", RolePermissionViewSet, basename="internal-role-permissions")
router.register("tasks", ProductionTaskViewSet, basename="internal-tasks")
router.register("checklist-templates", ChecklistTemplateViewSet, basename="internal-checklist-templates")
router.register("task-templates", TaskTemplateViewSet, basename="internal-task-templates")
router.register("task-recurrences", RecurrenceViewSet, basename="internal-task-recurrences")
router.register("task-occurrences", OccurrenceViewSet, basename="internal-task-occurrences")
router.register("task-saved-views", SavedViewViewSet, basename="internal-task-saved-views")
router.register("service-categories", CategoryViewSet, basename="internal-service-categories")
router.register("services", ServiceViewSet, basename="internal-services")
router.register("request-types", RequestTypeViewSet, basename="internal-request-types")
router.register("requests", ServiceRequestViewSet, basename="internal-requests")
router.register("sla/calendars", CalendarViewSet, basename="internal-sla-calendars")
router.register("sla/policies", PolicyViewSet, basename="internal-sla-policies")
router.register("sla/assignment-rules", AssignmentRuleViewSet, basename="internal-sla-assignment-rules")
router.register("sla/escalation-policies", EscalationPolicyViewSet, basename="internal-sla-escalation-policies")
router.register("sla/escalation-policy-versions", EscalationPolicyVersionViewSet, basename="internal-sla-escalation-policy-versions")
router.register("sla/escalation-bindings", EscalationBindingViewSet, basename="internal-sla-escalation-bindings")
router.register("sla", PreviewViewSet, basename="internal-sla-preview")
self_changes=SelfChangeRequestViewSet.as_view({"get":"list","post":"create"})
self_change_detail=SelfChangeRequestViewSet.as_view({"get":"retrieve"})
self_change_cancel=SelfChangeRequestViewSet.as_view({"post":"cancel"})
urlpatterns = [
    path("people/me/",MeView.as_view()), path("people/me/completeness/",CompletenessView.as_view()),
    path("people/me/first-login/", FirstLoginView.as_view()),
    path("people/<uuid:employee_id>/access/suspend/", AccountAccessView.as_view()),
    path("people/<uuid:employee_id>/access/restore/", AccountRestoreView.as_view()),
    path("people/<uuid:employee_id>/access/block/", AccountBlockView.as_view()),
    path("people/<uuid:employee_id>/access/reactivate/", AccountReactivateView.as_view()),
    path("people/me/organization/",OrganizationView.as_view()), path("people/me/teams/",TeamsView.as_view()),
    path("people/me/visibility/",VisibilityView.as_view()), path("people/me/avatar/",AvatarView.as_view()),
    path("people/me/change-requests/",self_changes),path("people/me/change-requests/<uuid:pk>/",self_change_detail),path("people/me/change-requests/<uuid:pk>/cancel/",self_change_cancel),
] + router.urls + [path("service-catalog/", ServiceCatalogView.as_view(), name="internal-service-catalog")]
