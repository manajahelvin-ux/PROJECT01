"""Quality admin configuration."""

from django.contrib import admin

from .models import Anomaly, QualityReport


@admin.register(QualityReport)
class QualityReportAdmin(admin.ModelAdmin):
    list_display = ("dataset", "global_score", "completeness", "accuracy", "consistency", "uniqueness", "validity")
    readonly_fields = ("id", "created_at")


@admin.register(Anomaly)
class AnomalyAdmin(admin.ModelAdmin):
    list_display = ("anomaly_type", "severity", "field_name", "dataset", "is_resolved", "created_at")
    list_filter = ("anomaly_type", "severity", "is_resolved")
    readonly_fields = ("id", "created_at")
