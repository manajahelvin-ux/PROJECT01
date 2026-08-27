"""
Quality models — Data quality reports and anomaly tracking.
"""

import uuid

from django.db import models


class QualityReport(models.Model):
    """Data quality score report for a dataset."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dataset = models.OneToOneField(
        "datasets.Dataset",
        on_delete=models.CASCADE,
        related_name="quality_report",
    )
    completeness = models.FloatField(default=0.0, help_text="0-100: % of fields filled")
    accuracy = models.FloatField(default=0.0, help_text="0-100: % of accurate values")
    consistency = models.FloatField(default=0.0, help_text="0-100: format consistency")
    uniqueness = models.FloatField(default=0.0, help_text="0-100: % unique records")
    validity = models.FloatField(default=0.0, help_text="0-100: % valid format values")
    global_score = models.FloatField(default=0.0, help_text="Weighted average /100")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "quality_reports"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Quality Report: {self.global_score}/100"

    def calculate_global_score(self):
        """Calculate weighted global quality score."""
        weights = {
            "completeness": 0.25,
            "accuracy": 0.25,
            "consistency": 0.20,
            "uniqueness": 0.15,
            "validity": 0.15,
        }
        self.global_score = round(
            self.completeness * weights["completeness"]
            + self.accuracy * weights["accuracy"]
            + self.consistency * weights["consistency"]
            + self.uniqueness * weights["uniqueness"]
            + self.validity * weights["validity"],
            1,
        )
        return self.global_score

    def save(self, *args, **kwargs):
        self.calculate_global_score()
        super().save(*args, **kwargs)


class Anomaly(models.Model):
    """A detected data anomaly."""

    class AnomalyType(models.TextChoices):
        MISSING_VALUE = "MISSING_VALUE", "Valeur manquante"
        INCONSISTENT_PRICE = "INCONSISTENT_PRICE", "Prix incohérent"
        INVALID_FORMAT = "INVALID_FORMAT", "Format invalide"
        INVALID_URL = "INVALID_URL", "URL invalide"
        INVALID_EMAIL = "INVALID_EMAIL", "Email invalide"
        DUPLICATE = "DUPLICATE", "Doublon"
        OUTLIER = "OUTLIER", "Valeur aberrante"
        EMPTY_RECORD = "EMPTY_RECORD", "Enregistrement vide"

    class Severity(models.TextChoices):
        LOW = "LOW", "Faible"
        MEDIUM = "MEDIUM", "Moyenne"
        HIGH = "HIGH", "Élevée"
        CRITICAL = "CRITICAL", "Critique"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dataset = models.ForeignKey(
        "datasets.Dataset",
        on_delete=models.CASCADE,
        related_name="anomalies",
    )
    record = models.ForeignKey(
        "datasets.DataRecord",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="anomalies",
    )
    anomaly_type = models.CharField(max_length=25, choices=AnomalyType.choices)
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.MEDIUM)
    field_name = models.CharField(max_length=100, blank=True, default="")
    description = models.TextField(blank=True, default="")
    suggestion = models.TextField(blank=True, default="")
    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "anomalies"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["dataset", "anomaly_type"]),
            models.Index(fields=["is_resolved"]),
        ]

    def __str__(self):
        return f"{self.get_anomaly_type_display()} — {self.field_name}"
