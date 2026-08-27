"""
Scraping models — Website management and HTTP fetch tracking.
"""

import uuid

from django.db import models


class Website(models.Model):
    """A target website for data extraction."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="websites",
    )
    name = models.CharField(max_length=255)
    base_url = models.URLField(max_length=1000)
    robots_txt_allowed = models.BooleanField(default=True)
    crawl_delay = models.FloatField(default=2.0, help_text="Seconds between requests")
    max_concurrent = models.IntegerField(default=2)
    last_scraped_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "websites"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.base_url})"
