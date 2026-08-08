from rest_framework.routers import DefaultRouter

from .views import CategoryViewSet, MaterialViewSet, TagViewSet

router = DefaultRouter()
router.register("categories", CategoryViewSet, basename="knowledge-category")
router.register("tags", TagViewSet, basename="knowledge-tag")
router.register("materials", MaterialViewSet, basename="knowledge-material")
urlpatterns = router.urls
