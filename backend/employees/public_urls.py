from django.urls import path
from .onboarding_api import PublicActivationView, PublicRegistrationView
from .onboarding_phase24_api import PublicInvitationAcceptView, PublicInvitationValidateView

urlpatterns = [
    path("register/", PublicRegistrationView.as_view(), name="public-register"),
    path("activate/<str:token>/", PublicActivationView.as_view(), name="public-activate"),
    path("auth/invitations/validate/", PublicInvitationValidateView.as_view(), name="invitation-validate"),
    path("auth/invitations/accept/", PublicInvitationAcceptView.as_view(), name="invitation-accept"),
]
