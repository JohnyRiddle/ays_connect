from django.urls import path, include
from .registration_api import Submit
from .registration_urls import public_patterns
from .onboarding_api import PublicActivationView, PublicRegistrationView
from .onboarding_phase24_api import PublicInvitationAcceptView, PublicInvitationValidateView

urlpatterns = [
    path("register/", Submit.as_view(), name="public-register"),
    path("registration/", include(public_patterns)),
    path("activate/<str:token>/", PublicActivationView.as_view(), name="public-activate"),
    path("auth/invitations/validate/", PublicInvitationValidateView.as_view(), name="invitation-validate"),
    path("auth/invitations/accept/", PublicInvitationAcceptView.as_view(), name="invitation-accept"),
]
