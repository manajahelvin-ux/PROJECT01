"""
Exports models — Export job tracking for multiple formats.
"""

import uuid

from django.conf import settings
from django.db import models


class ExportJob(models.Model):
    """A data export task."""

    class Format(models.TextChoices):
        CSV = "csv", "CSV"
        XLSX = "xlsx", "Excel XLSX"
        JSON = "json", "JSON"
        XML = "xml", "XML"
        PARQUET = "parquet", "Parquet"

    class Status(models.TextChoices):
        PENDING = "PENDING", "En attente"
        PROCESSING = "PROCESSING", "En cours"
        COMPLETED = "COMPLETED", "Terminé"
        FAILED = "FAILED", "Échoué"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dataset = models.ForeignKey(
        "datasets.Dataset",
        on_delete=models.CASCADE,
        related_name="export_jobs",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )
    export_format = models.CharField(max_length=10, choices=Format.choices)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    file_path = models.CharField(max_length=500, blank=True, default="")
    file_size_bytes = models.BigIntegerField(default=0)
    total_records = models.IntegerField(default=0)
    valid_only = models.BooleanField(default=False, help_text="Export only validated records")
    error_message = models.TextField(blank=True, default="")
    celery_task_id = models.CharField(max_length=255, blank=True, default="")
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "export_jobs"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Export {self.get_export_format_display()} — {self.status}"
