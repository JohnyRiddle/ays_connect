from django.urls import path
from rest_framework_simplejwt.views import TokenBlacklistView
from .views import ActiveTokenRefreshView, LoginView, MeView
urlpatterns = [path("login/", LoginView.as_view()), path("refresh/", ActiveTokenRefreshView.as_view()), path("logout/", TokenBlacklistView.as_view()), path("me/", MeView.as_view())]
