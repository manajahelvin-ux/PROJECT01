"""Knowledge Base admin configuration."""

from django.contrib import admin

from .models import KnowledgeArticle


@admin.register(KnowledgeArticle)
class KnowledgeArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "author", "is_published", "view_count", "updated_at")
    list_filter = ("category", "is_published")
    search_fields = ("title", "content", "tags")
    readonly_fields = ("id", "created_at", "updated_at")
