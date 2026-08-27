"""Datasets admin configuration."""

from django.contrib import admin

from .models import DataField, DataRecord, Dataset


class DataFieldInline(admin.TabularInline):
    model = DataField
    extra = 0


@admin.register(Dataset)
class DatasetAdmin(admin.ModelAdmin):
    list_display = ("name", "project", "status", "total_records", "avg_quality_score", "created_at")
    list_filter = ("status", "project")
    search_fields = ("name",)
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [DataFieldInline]


@admin.register(DataRecord)
class DataRecordAdmin(admin.ModelAdmin):
    list_display = ("id", "dataset", "validation_status", "quality_score", "is_duplicate", "extracted_at")
    list_filter = ("validation_status", "is_duplicate", "dataset")
    readonly_fields = ("id", "extracted_at")
