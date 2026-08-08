from rest_framework.routers import DefaultRouter
from .views import SensorViewSet
router=DefaultRouter();router.register("",SensorViewSet,basename="sensor");urlpatterns=router.urls
