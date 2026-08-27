"""
Knowledge Base models — Internal articles for team knowledge sharing.
"""

import uuid

from django.conf import settings
from django.db import models


class KnowledgeArticle(models.Model):
    """An article in the internal knowledge base."""

    class SiteCategory(models.TextChoices):
        ECOMMERCE = "ECOMMERCE", "E-commerce"
        DIRECTORY = "DIRECTORY", "Annuaire"
        JOB_BOARD = "JOB_BOARD", "Offres d'emploi"
        NEWS = "NEWS", "Actualités"
        GENERAL = "GENERAL", "Général"
        TIPS = "TIPS", "Astuces"
        WARNINGS = "WARNINGS", "Pièges"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    content = models.TextField()
    category = models.CharField(max_length=15, choices=SiteCategory.choices, default=SiteCategory.GENERAL)
    tags = models.JSONField(default=list, blank=True, help_text="List of tags")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="knowledge_articles",
    )
    is_published = models.BooleanField(default=True)
    view_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "knowledge_articles"
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title
