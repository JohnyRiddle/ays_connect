from django.urls import path
from .views import ManagementDashboardView,MyPerformanceView
urlpatterns=[path("me/",MyPerformanceView.as_view()),path("management/",ManagementDashboardView.as_view())]
