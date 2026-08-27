"""Projects admin configuration."""

from django.contrib import admin

from .models import Project, ProjectMember


class ProjectMemberInline(admin.TabularInline):
    model = ProjectMember
    extra = 0
    autocomplete_fields = ["user"]


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "category", "status", "created_at", "updated_at")
    list_filter = ("status", "category", "created_at")
    search_fields = ("name", "description", "owner__username")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [ProjectMemberInline]
    date_hierarchy = "created_at"
