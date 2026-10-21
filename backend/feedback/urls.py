from django.urls import path
from .views import SubmitView, CapabilitiesView, OwnerList, OwnerDetail, RetryView

urlpatterns = [
    path("submit/", SubmitView.as_view()),
    path("capabilities/", CapabilitiesView.as_view()),
    path("", OwnerList.as_view()),
    path("<uuid:pk>/", OwnerDetail.as_view()),
    path("<uuid:pk>/retry/", RetryView.as_view()),
]
