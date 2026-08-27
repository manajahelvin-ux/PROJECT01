"""
Extraction models — Configuration, execution, selectors, and versioning.
"""

import uuid

from django.conf import settings
from django.db import models


class ExtractionConfig(models.Model):
    """Configuration for a data extraction (URL patterns, selectors, render mode)."""

    class RenderMode(models.TextChoices):
        STATIC = "static", "Statique (HTTP)"
        JAVASCRIPT = "javascript", "JavaScript (Playwright)"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="extraction_configs",
    )
    website = models.ForeignKey(
        "scraping.Website",
        on_delete=models.CASCADE,
        related_name="extraction_configs",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=255)
    target_url = models.URLField(max_length=2000)
    render_mode = models.CharField(
        max_length=12,
        choices=RenderMode.choices,
        default=RenderMode.STATIC,
    )
    wait_for_selector = models.CharField(max_length=500, blank=True, default="")
    pagination_selector = models.CharField(max_length=500, blank=True, default="")
    max_pages = models.IntegerField(default=1)
    request_delay = models.FloatField(default=2.0)
    is_active = models.BooleanField(default=True)
    current_version = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_extractions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "extraction_configs"
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.name} (v{self.current_version})"


class ExtractionConfigVersion(models.Model):
    """Versioned snapshot of an extraction configuration for rollback."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    config = models.ForeignKey(
        ExtractionConfig,
        on_delete=models.CASCADE,
        related_name="versions",
    )
    version_number = models.PositiveIntegerField()
    snapshot = models.JSONField(default=dict, help_text="Full config snapshot at this version")
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )
    change_note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "extraction_config_versions"
        ordering = ["-version_number"]
        unique_together = ("config", "version_number")

    def __str__(self):
        return f"{self.config.name} v{self.version_number}"


class Selector(models.Model):
    """A field selector within an extraction configuration."""

    class SelectorType(models.TextChoices):
        TEXT = "text", "Texte"
        NUMBER = "number", "Nombre"
        PRICE = "price", "Prix"
        DATE = "date", "Date"
        URL = "url", "URL"
        EMAIL = "email", "Email"
        PHONE = "phone", "Téléphone"
        BOOLEAN = "boolean", "Booléen"
        HTML = "html", "HTML brut"
        IMAGE = "image", "Image"
        JSON = "json", "JSON"
        LIST = "list", "Liste"

    class Method(models.TextChoices):
        CSS = "css", "CSS Selector"
        XPATH = "xpath", "XPath"
        REGEX = "regex", "Regex"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    config = models.ForeignKey(
        ExtractionConfig,
        on_delete=models.CASCADE,
        related_name="selectors",
    )
    name = models.CharField(max_length=100)
    selector_type = models.CharField(max_length=10, choices=SelectorType.choices, default=SelectorType.TEXT)
    method = models.CharField(max_length=5, choices=Method.choices, default=Method.CSS)
    selector_value = models.CharField(max_length=1000)
    is_required = models.BooleanField(default=False)
    default_value = models.CharField(max_length=500, blank=True, default="")
    transformation = models.TextField(blank=True, default="", help_text="Python expression for data transformation")
    attribute = models.CharField(max_length=100, blank=True, default="", help_text="HTML attribute to extract (href, src, etc.)")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "selectors"
        ordering = ["order", "name"]

    def __str__(self):
        return f"{self.name} ({self.method}: {self.selector_value})"


class ExtractionJob(models.Model):
    """A single execution of an extraction configuration."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "En attente"
        RUNNING = "RUNNING", "En cours"
        SUCCESS = "SUCCESS", "Succès"
        FAILED = "FAILED", "Échoué"
        CANCELLED = "CANCELLED", "Annulé"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    config = models.ForeignKey(
        ExtractionConfig,
        on_delete=models.CASCADE,
        related_name="jobs",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="extraction_jobs",
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    pages_scraped = models.IntegerField(default=0)
    rows_extracted = models.IntegerField(default=0)
    rows_valid = models.IntegerField(default=0)
    rows_invalid = models.IntegerField(default=0)
    error_message = models.TextField(blank=True, default="")
    result_summary = models.JSONField(default=dict, blank=True)
    celery_task_id = models.CharField(max_length=255, blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "extraction_jobs"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Job {self.id} — {self.config.name} ({self.status})"

    @property
    def duration_seconds(self):
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class ScheduledJob(models.Model):
    """Recurring extraction schedule powered by Celery Beat."""

    class Frequency(models.TextChoices):
        HOURLY = "hourly", "Toutes les heures"
        DAILY = "daily", "Quotidien"
        WEEKLY = "weekly", "Hebdomadaire"
        MONTHLY = "monthly", "Mensuel"
        CUSTOM = "custom", "Personnalisé (cron)"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    config = models.ForeignKey(
        ExtractionConfig,
        on_delete=models.CASCADE,
        related_name="scheduled_jobs",
    )
    name = models.CharField(max_length=255)
    frequency = models.CharField(max_length=10, choices=Frequency.choices, default=Frequency.DAILY)
    cron_expression = models.CharField(max_length=100, blank=True, default="")
    is_active = models.BooleanField(default=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    next_run_at = models.DateTimeField(null=True, blank=True)
    total_runs = models.IntegerField(default=0)
    success_count = models.IntegerField(default=0)
    fail_count = models.IntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "scheduled_jobs"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.get_frequency_display()})"
