from rest_framework.generics import RetrieveAPIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .serializers import ActiveTokenRefreshSerializer, EmailTokenSerializer, ProfileSerializer

class LoginView(TokenObtainPairView):
    serializer_class = EmailTokenSerializer
    throttle_scope = "login"
class ActiveTokenRefreshView(TokenRefreshView): serializer_class = ActiveTokenRefreshSerializer
class MeView(RetrieveAPIView):
    serializer_class = ProfileSerializer
    def get_object(self): return self.request.user
