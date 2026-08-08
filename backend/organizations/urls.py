from django.urls import path
from .views import OrganizationTreeView
urlpatterns = [path("tree/", OrganizationTreeView.as_view())]
