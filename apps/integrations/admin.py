"""Integrations admin configuration."""

from django.contrib import admin

from .models import Webhook, WebhookDelivery


class WebhookDeliveryInline(admin.TabularInline):
    model = WebhookDelivery
    extra = 0
    readonly_fields = ("id", "created_at")


@admin.register(Webhook)
class WebhookAdmin(admin.ModelAdmin):
    list_display = ("name", "url", "project", "is_active", "trigger_on_extraction", "created_at")
    list_filter = ("is_active", "trigger_on_extraction", "trigger_on_export")
    search_fields = ("name", "url")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [WebhookDeliveryInline]
