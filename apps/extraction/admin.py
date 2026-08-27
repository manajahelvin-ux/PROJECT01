"""Extraction admin configuration."""

from django.contrib import admin

from .models import ExtractionConfig, ExtractionConfigVersion, ExtractionJob, ScheduledJob, Selector


class SelectorInline(admin.TabularInline):
    model = Selector
    extra = 0


@admin.register(ExtractionConfig)
class ExtractionConfigAdmin(admin.ModelAdmin):
    list_display = ("name", "project", "render_mode", "is_active", "current_version", "created_at")
    list_filter = ("render_mode", "is_active", "project")
    search_fields = ("name", "target_url")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [SelectorInline]


@admin.register(ExtractionConfigVersion)
class ExtractionConfigVersionAdmin(admin.ModelAdmin):
    list_display = ("config", "version_number", "changed_by", "created_at")
    list_filter = ("config",)
    readonly_fields = ("id", "created_at")


@admin.register(ExtractionJob)
class ExtractionJobAdmin(admin.ModelAdmin):
    list_display = ("config", "project", "status", "pages_scraped", "rows_extracted", "created_at")
    list_filter = ("status", "project", "created_at")
    search_fields = ("config__name",)
    readonly_fields = ("id", "created_at")
    actions = ["cancel_jobs"]

    @admin.action(description="Cancel selected jobs")
    def cancel_jobs(self, request, queryset):
        updated = queryset.filter(status="PENDING").update(status="CANCELLED")
        self.message_user(request, f"{updated} jobs cancelled.")


@admin.register(ScheduledJob)
class ScheduledJobAdmin(admin.ModelAdmin):
    list_display = ("name", "config", "frequency", "is_active", "last_run_at", "total_runs")
    list_filter = ("frequency", "is_active")
    search_fields = ("name", "config__name")
    readonly_fields = ("id", "created_at", "updated_at")
    actions = ["activate", "deactivate"]

    @admin.action(description="Activate selected schedules")
    def activate(self, request, queryset):
        queryset.update(is_active=True)

    @admin.action(description="Deactivate selected schedules")
    def deactivate(self, request, queryset):
        queryset.update(is_active=False)
