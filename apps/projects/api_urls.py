"""Projects API URL routes."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .api_views import ProjectViewSet

router = DefaultRouter()
router.register(r"projects", ProjectViewSet, basename="api-project")

urlpatterns = router.urls
