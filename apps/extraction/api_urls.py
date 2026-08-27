"""Extraction API URL routes."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .api_views import ExtractionConfigViewSet, ExtractionJobViewSet

router = DefaultRouter()
router.register(r"extractions", ExtractionConfigViewSet, basename="api-extraction")
router.register(r"extraction-jobs", ExtractionJobViewSet, basename="api-extraction-job")

urlpatterns = router.urls
