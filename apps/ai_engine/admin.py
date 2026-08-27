"""AI Engine admin configuration."""

from django.contrib import admin

from .models import AIRequest, AIResponse


@admin.register(AIRequest)
class AIRequestAdmin(admin.ModelAdmin):
    list_display = ("prompt_type", "model_used", "user", "success", "duration_ms", "created_at")
    list_filter = ("prompt_type", "success", "model_used")
    readonly_fields = ("id", "created_at")


@admin.register(AIResponse)
class AIResponseAdmin(admin.ModelAdmin):
    list_display = ("request", "confidence_level", "confidence_score", "is_valid", "created_at")
    list_filter = ("confidence_level", "is_valid")
    readonly_fields = ("id", "created_at")
