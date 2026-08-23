from django.contrib import admin
from django.urls import include, path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    return Response({"status": "ok", "service": "ays-connect"})

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/health/", health),
    path("api/v1/auth/", include("accounts.urls")),
    path("api/v1/organization/", include("organizations.urls")),
    path("api/v1/employees/", include("employees.urls")),
    path("api/v1/tasks/", include("tasks.urls")),
    path("api/v1/checklists/", include("checklists.urls")),
    path("api/v1/sensors/", include("sensors.urls")),
    path("api/v1/incidents/", include("incidents.urls")),
    path("api/v1/analytics/", include("analytics.urls")),
    path("api/v1/notifications/", include("notifications.urls")),
    path("api/v1/knowledge/", include("knowledge_base.urls")),
    path("api/v1/learning/", include("learning.urls")),
    path("api/internal/v1/", include("access_control.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]
