"""
Authentication models - Custom User model with roles.
"""

import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom User model with role-based access control.

    Roles:
    - ADMIN: Full access, user management, quota management.
    - OPERATOR: Create/manage projects, extractions, configurations.
    - VIEWER: View results and statistics only.
    """

    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Administrator"
        OPERATOR = "OPERATOR", "Operator"
        VIEWER = "VIEWER", "Viewer"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.VIEWER,
        help_text="User role for permission management.",
    )
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    bio = models.TextField(max_length=500, blank=True, default="")
    phone = models.CharField(max_length=20, blank=True, default="")
    two_factor_enabled = models.BooleanField(default=False)
    last_activity = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "users"
        ordering = ["-date_joined"]

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    @property
    def is_admin(self) -> bool:
        return self.role == self.Role.ADMIN

    @property
    def is_operator(self) -> bool:
        return self.role == self.Role.OPERATOR

    @property
    def is_viewer(self) -> bool:
        return self.role == self.Role.VIEWER
