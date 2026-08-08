from rest_framework.generics import RetrieveAPIView
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import EmailTokenSerializer, ProfileSerializer

class LoginView(TokenObtainPairView): serializer_class = EmailTokenSerializer
class MeView(RetrieveAPIView):
    serializer_class = ProfileSerializer
    def get_object(self): return self.request.user
