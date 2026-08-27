"""
Integrations models — Webhooks and external service connectors.
"""

import uuid

from django.conf import settings
from django.db import models


class Webhook(models.Model):
    """Configured outgoing webhook."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="webhooks",
    )
    name = models.CharField(max_length=255)
    url = models.URLField(max_length=2000)
    secret = models.CharField(max_length=255, blank=True, default="", help_text="HMAC signing secret")
    is_active = models.BooleanField(default=True)
    trigger_on_extraction = models.BooleanField(default=True)
    trigger_on_export = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "webhooks"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} → {self.url}"


class WebhookDelivery(models.Model):
    """Log of a webhook delivery attempt."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "En attente"
        SUCCESS = "SUCCESS", "Succès"
        FAILED = "FAILED", "Échoué"
        RETRYING = "RETRYING", "Retry"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    webhook = models.ForeignKey(
        Webhook,
        on_delete=models.CASCADE,
        related_name="deliveries",
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    payload = models.JSONField(default=dict)
    response_status = models.IntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True, default="")
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)
    error_message = models.TextField(blank=True, default="")
    delivered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "webhook_deliveries"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Delivery {self.status} → {self.webhook.name}"
