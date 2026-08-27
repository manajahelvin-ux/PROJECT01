"""Scraping admin configuration."""

from django.contrib import admin

from .models import Website


@admin.register(Website)
class WebsiteAdmin(admin.ModelAdmin):
    list_display = ("name", "base_url", "project", "crawl_delay", "last_scraped_at")
    list_filter = ("project", "robots_txt_allowed")
    search_fields = ("name", "base_url")
    readonly_fields = ("id", "created_at", "updated_at")
