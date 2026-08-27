"""
Projects models — Project management and team collaboration.
"""

import uuid

from django.conf import settings
from django.db import models


class Project(models.Model):
    """A data extraction project grouping websites, configs, and datasets."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Brouillon"
        ACTIVE = "ACTIVE", "Actif"
        PAUSED = "PAUSED", "En pause"
        COMPLETED = "COMPLETED", "Terminé"
        ERROR = "ERROR", "Erreur"
        ARCHIVED = "ARCHIVED", "Archivé"

    class Category(models.TextChoices):
        ECOMMERCE = "ECOMMERCE", "E-commerce"
        DIRECTORY = "DIRECTORY", "Annuaire"
        JOB_BOARD = "JOB_BOARD", "Offres d'emploi"
        NEWS = "NEWS", "Actualités"
        REAL_ESTATE = "REAL_ESTATE", "Immobilier"
        OTHER = "OTHER", "Autre"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_projects",
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="ProjectMember",
        related_name="member_projects",
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "projects"
        ordering = ["-updated_at"]

    def __str__(self):
        return self.name


class ProjectMember(models.Model):
    """Team membership for a project with role-based access."""

    class MemberRole(models.TextChoices):
        OWNER = "OWNER", "Propriétaire"
        EDITOR = "EDITOR", "Éditeur"
        VIEWER = "VIEWER", "Lecteur"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="project_members")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="project_memberships",
    )
    role = models.CharField(max_length=10, choices=MemberRole.choices, default=MemberRole.VIEWER)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "project_members"
        unique_together = ("project", "user")

    def __str__(self):
        return f"{self.user.username} — {self.project.name} ({self.get_role_display()})"
