from rest_framework.routers import DefaultRouter
from .views import DeliveryViewSet,NotificationViewSet,PreferenceViewSet,QuietHoursViewSet,TemplateViewSet
router=DefaultRouter();router.register("templates",TemplateViewSet,basename="notification-template");router.register("preferences",PreferenceViewSet,basename="notification-preference");router.register("quiet-hours",QuietHoursViewSet,basename="notification-quiet-hours");router.register("deliveries",DeliveryViewSet,basename="notification-delivery");router.register("",NotificationViewSet,basename="notification");urlpatterns=router.urls
