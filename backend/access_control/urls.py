from rest_framework.routers import DefaultRouter
from employees.internal_api import AssignmentTargetViewSet, EmployeeViewSet, FunctionalGroupViewSet, PositionViewSet
from organizations.internal_api import LegalEntityViewSet, LocationViewSet, OrgUnitViewSet
from .views import PermissionViewSet, RolePermissionViewSet, RoleViewSet
from work_tasks.views import ChecklistTemplateViewSet, ProductionTaskViewSet
from work_tasks.automation_views import OccurrenceViewSet, RecurrenceViewSet, SavedViewViewSet, TaskTemplateViewSet
from service_requests.views import CategoryViewSet, ServiceViewSet, RequestTypeViewSet, ServiceCatalogView, ServiceRequestViewSet
from django.urls import path
from sla.views import CalendarViewSet, PolicyViewSet, AssignmentRuleViewSet, PreviewViewSet, EscalationPolicyViewSet, EscalationPolicyVersionViewSet, EscalationBindingViewSet

router = DefaultRouter()
router.register("employees", EmployeeViewSet, basename="internal-employees")
router.register("positions", PositionViewSet, basename="internal-positions")
router.register("legal-entities", LegalEntityViewSet, basename="internal-legal-entities")
router.register("org-units", OrgUnitViewSet, basename="internal-org-units")
router.register("locations", LocationViewSet, basename="internal-locations")
router.register("functional-groups", FunctionalGroupViewSet, basename="internal-functional-groups")
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
urlpatterns = router.urls + [path("service-catalog/", ServiceCatalogView.as_view(), name="internal-service-catalog")]
