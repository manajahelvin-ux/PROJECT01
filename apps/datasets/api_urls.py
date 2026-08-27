"""Datasets API URL routes."""

from django.urls import path
from rest_framework.routers import DefaultRouter

from .api_views import DatasetViewSet

router = DefaultRouter()
router.register(r"datasets", DatasetViewSet, basename="api-dataset")

urlpatterns = router.urls
