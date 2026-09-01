from django.urls import path
from .onboarding_api import PublicActivationView, PublicRegistrationView

urlpatterns = [
    path("register/", PublicRegistrationView.as_view(), name="public-register"),
    path("activate/<str:token>/", PublicActivationView.as_view(), name="public-activate"),
]
