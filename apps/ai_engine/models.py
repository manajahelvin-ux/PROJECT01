"""
AI Engine models — Tracking AI requests, responses, and confidence scores.
"""

import uuid

from django.conf import settings
from django.db import models


class AIRequest(models.Model):
    """Log of an AI request sent to OpenRouter."""

    class PromptType(models.TextChoices):
        ANALYZE_PAGE = "analyze_page", "Analyse de page"
        STRUCTURE_DATA = "structure_data", "Structuration"
        CLEAN_DATA = "clean_data", "Nettoyage"
        QUALITY_CHECK = "quality_check", "Contrôle qualité"
        ANOMALY_DETECT = "anomaly_detect", "Détection anomalies"
        GENERATE_SCHEMA = "generate_schema", "Génération schéma"
        CHAT = "chat", "Chat assistant"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="ai_requests",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_requests",
    )
    prompt_type = models.CharField(max_length=20, choices=PromptType.choices)
    model_used = models.CharField(max_length=255)
    prompt_content = models.TextField()
    tokens_input = models.IntegerField(default=0)
    tokens_output = models.IntegerField(default=0)
    duration_ms = models.IntegerField(default=0)
    success = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ai_requests"
        ordering = ["-created_at"]

    def __str__(self):
        return f"AI Request {self.prompt_type} ({self.created_at})"


class AIResponse(models.Model):
    """Parsed and validated AI response."""

    class ConfidenceLevel(models.TextChoices):
        HIGH = "HIGH", "Haute (>=90%)"
        MEDIUM = "MEDIUM", "Moyenne (70-89%)"
        LOW = "LOW", "Faible (<70%)"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.OneToOneField(
        AIRequest,
        on_delete=models.CASCADE,
        related_name="response",
    )
    raw_response = models.TextField()
    parsed_data = models.JSONField(default=dict)
    confidence_score = models.FloatField(default=0.0)
    confidence_level = models.CharField(
        max_length=10,
        choices=ConfidenceLevel.choices,
        default=ConfidenceLevel.MEDIUM,
    )
    is_valid = models.BooleanField(default=True)
    validation_errors = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ai_responses"
        ordering = ["-created_at"]

    def __str__(self):
        return f"AI Response (confidence: {self.confidence_score}%)"

    def save(self, *args, **kwargs):
        if self.confidence_score >= 90:
            self.confidence_level = self.ConfidenceLevel.HIGH
        elif self.confidence_score >= 70:
            self.confidence_level = self.ConfidenceLevel.MEDIUM
        else:
            self.confidence_level = self.ConfidenceLevel.LOW
        super().save(*args, **kwargs)
