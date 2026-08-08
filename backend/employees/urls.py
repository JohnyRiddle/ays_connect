from django.urls import path
from .views import EmployeeDetailView, EmployeeListView, PersonalDashboardView
urlpatterns = [path("dashboard/", PersonalDashboardView.as_view()), path("", EmployeeListView.as_view()), path("<int:pk>/", EmployeeDetailView.as_view())]
