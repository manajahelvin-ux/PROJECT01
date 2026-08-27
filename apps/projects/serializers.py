"""Shared API serializers."""

from rest_framework import serializers

from apps.authentication.models import User
from apps.datasets.models import DataRecord, Dataset
from apps.extraction.models import ExtractionConfig, ExtractionJob, Selector
from apps.projects.models import Project


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "role", "date_joined"]


class ProjectSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)

    class Meta:
        model = Project
        fields = ["id", "name", "description", "category", "status", "owner", "created_at", "updated_at"]
        read_only_fields = ["id", "owner", "created_at", "updated_at"]


class SelectorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Selector
        fields = ["id", "name", "selector_type", "method", "selector_value", "is_required", "order"]


class ExtractionConfigSerializer(serializers.ModelSerializer):
    selectors = SelectorSerializer(many=True, read_only=True)

    class Meta:
        model = ExtractionConfig
        fields = ["id", "name", "target_url", "render_mode", "wait_for_selector", "max_pages", "is_active", "current_version", "selectors", "created_at"]
        read_only_fields = ["id", "current_version", "created_at"]


class ExtractionJobSerializer(serializers.ModelSerializer):
    config_name = serializers.CharField(source="config.name", read_only=True)
    duration = serializers.FloatField(source="duration_seconds", read_only=True)

    class Meta:
        model = ExtractionJob
        fields = ["id", "config_name", "status", "pages_scraped", "rows_extracted", "rows_valid", "rows_invalid", "error_message", "duration", "created_at"]


class DatasetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dataset
        fields = ["id", "name", "status", "total_records", "valid_records", "invalid_records", "duplicate_count", "avg_quality_score", "created_at"]


class DataRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataRecord
        fields = ["id", "data", "validation_status", "quality_score", "is_duplicate", "source_url", "extracted_at"]
