from django.urls import path

from .views import EmployeeSummaryView, LegalEntitySummaryView, LocationSummaryView, MeView, MetricDefinitionView, OrgUnitEmployeesView, OrgUnitSummaryView, OverviewView

urlpatterns = [
    path("me/", MeView.as_view()),
    path("employees/<uuid:employee_id>/summary/", EmployeeSummaryView.as_view()),
    path("org-units/<uuid:dimension_id>/summary/", OrgUnitSummaryView.as_view()),
    path("org-units/<uuid:dimension_id>/employees/", OrgUnitEmployeesView.as_view()),
    path("locations/<uuid:dimension_id>/summary/", LocationSummaryView.as_view()),
    path("legal-entities/<uuid:dimension_id>/summary/", LegalEntitySummaryView.as_view()),
    path("overview/", OverviewView.as_view()),
    path("metrics/", MetricDefinitionView.as_view()),
    path("metrics/<str:code>/", MetricDefinitionView.as_view()),
]
