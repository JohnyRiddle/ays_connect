from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .registration_api import (PublicLocations, Submit, Confirm, OwnStatus, Resend,
    Cancel, InviteContext, Requests, Invitations, EmployeeObjects, EmployeeAccessScope, EmployeeEmployment)

router = DefaultRouter()
router.register("requests", Requests, basename="object-registration-request")
router.register("invitations", Invitations, basename="object-registration-invitation")
urlpatterns = [path("", include(router.urls)),
    path("employees/<uuid:employee_id>/objects/", EmployeeObjects.as_view()),
    path("employees/<uuid:employee_id>/access/", EmployeeAccessScope.as_view()),
    path("employees/<uuid:employee_id>/employment/", EmployeeEmployment.as_view())]

public_patterns = [path("locations/", PublicLocations.as_view()),
    path("submit/", Submit.as_view()), path("confirm/", Confirm.as_view()),
    path("status/", OwnStatus.as_view()), path("resend/", Resend.as_view()),
    path("cancel/", Cancel.as_view()), path("invitation/", InviteContext.as_view())]
