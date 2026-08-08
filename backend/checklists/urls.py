from rest_framework.routers import DefaultRouter
from .views import RunViewSet,TemplateViewSet
router=DefaultRouter();router.register("templates",TemplateViewSet,basename="checklist-template");router.register("runs",RunViewSet,basename="checklist-run")
urlpatterns=router.urls
