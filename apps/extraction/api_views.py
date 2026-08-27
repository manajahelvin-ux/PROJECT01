"""Extraction API views."""

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import ExtractionConfig, ExtractionJob
from apps.projects.serializers import ExtractionConfigSerializer, ExtractionJobSerializer
from .services import run_extraction, test_extraction


class ExtractionConfigViewSet(viewsets.ModelViewSet):
    serializer_class = ExtractionConfigSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ExtractionConfig.objects.filter(project__owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["post"])
    def test(self, request, pk=None):
        config = self.get_object()
        result = test_extraction(config)
        return Response(result)

    @action(detail=True, methods=["post"])
    def run(self, request, pk=None):
        config = self.get_object()
        job = ExtractionJob.objects.create(config=config, project=config.project, created_by=request.user)
        result = run_extraction(job)
        return Response(result)


class ExtractionJobViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ExtractionJobSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ExtractionJob.objects.filter(project__owner=self.request.user)
