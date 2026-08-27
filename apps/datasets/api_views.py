"""Datasets API views."""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import DataRecord, Dataset
from apps.projects.serializers import DataRecordSerializer, DatasetSerializer


class DatasetViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DatasetSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Dataset.objects.filter(project__owner=self.request.user)


class DataRecordViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DataRecordSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        dataset_id = self.kwargs.get("dataset_pk")
        return DataRecord.objects.filter(dataset_id=dataset_id)
