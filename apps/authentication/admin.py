"""Authentication admin configuration."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "role", "is_active", "date_joined")
    list_filter = ("role", "is_active", "is_staff", "date_joined")
    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("-date_joined",)

    fieldsets = BaseUserAdmin.fieldsets + (
        ("Profile", {"fields": ("role", "avatar", "bio", "phone", "two_factor_enabled")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Role", {"fields": ("role",)}),
    )
