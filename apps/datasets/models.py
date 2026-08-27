"""
Datasets models — Extracted data records and fields.
"""

import uuid

from django.db import models


class Dataset(models.Model):
    """A collection of extracted data records."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "En cours"
        READY = "READY", "Prêt"
        EXPORTED = "EXPORTED", "Exporté"
        ARCHIVED = "ARCHIVED", "Archivé"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    extraction_job = models.OneToOneField(
        "extraction.ExtractionJob",
        on_delete=models.CASCADE,
        related_name="dataset",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="datasets",
    )
    name = models.CharField(max_length=255)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    total_records = models.IntegerField(default=0)
    valid_records = models.IntegerField(default=0)
    invalid_records = models.IntegerField(default=0)
    duplicate_count = models.IntegerField(default=0)
    avg_quality_score = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "datasets"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.total_records} records)"


class DataField(models.Model):
    """Schema definition for fields in a dataset."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dataset = models.ForeignKey(
        Dataset,
        on_delete=models.CASCADE,
        related_name="fields",
    )
    name = models.CharField(max_length=100)
    field_type = models.CharField(max_length=50, default="text")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "data_fields"
        ordering = ["order"]

    def __str__(self):
        return f"{self.name} ({self.field_type})"


class DataRecord(models.Model):
    """A single row of extracted data."""

    class ValidationStatus(models.TextChoices):
        VALID = "VALID", "Valide"
        INVALID = "INVALID", "Invalide"
        WARNING = "WARNING", "Attention"
        REVIEW = "REVIEW", "À vérifier"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dataset = models.ForeignKey(
        Dataset,
        on_delete=models.CASCADE,
        related_name="records",
    )
    data = models.JSONField(default=dict)
    validation_status = models.CharField(
        max_length=10,
        choices=ValidationStatus.choices,
        default=ValidationStatus.VALID,
    )
    quality_score = models.FloatField(default=0.0)
    is_duplicate = models.BooleanField(default=False)
    duplicate_of = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="duplicates",
    )
    raw_html = models.TextField(blank=True, default="")
    source_url = models.URLField(max_length=2000, blank=True, default="")
    extracted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "data_records"
        ordering = ["extracted_at"]
        indexes = [
            models.Index(fields=["dataset", "validation_status"]),
            models.Index(fields=["dataset", "is_duplicate"]),
        ]

    def __str__(self):
        return f"Record {self.id} — {self.validation_status}"
