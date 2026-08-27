"""Exports admin configuration."""

from django.contrib import admin

from .models import ExportJob


@admin.register(ExportJob)
class ExportJobAdmin(admin.ModelAdmin):
    list_display = ("dataset", "export_format", "status", "total_records", "file_size_bytes", "created_at")
    list_filter = ("export_format", "status")
    readonly_fields = ("id", "created_at")
