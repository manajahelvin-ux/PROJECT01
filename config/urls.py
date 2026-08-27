"""
DataExtract AI - URL Configuration
====================================
Root URL configuration for all environments.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular import views as drf_spectacular_views

urlpatterns = [
    # --- Admin ---
    path("admin/", admin.site.urls),

    # --- Health Check ---
    path("health/", include("apps.dashboard.health_urls")),

    # --- API ---
    path("api/", include("apps.projects.api_urls")),
    path("api/", include("apps.extraction.api_urls")),
    path("api/", include("apps.datasets.api_urls")),
    path("api/", include("apps.ai_engine.api_urls")),
    path("api/", include("apps.quality.api_urls")),
    path("api/", include("apps.exports.api_urls")),
    path("api/", include("apps.integrations.api_urls")),
    path("api/", include("apps.scheduling.api_urls")),
    path("api/", include("apps.knowledge_base.api_urls")),

    # --- API Documentation ---
    path("api/docs/schema/", drf_spectacular_views.SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/swagger/", drf_spectacular_views.SpectacularSwaggerView.as_view(url_name="schema"), name="swagger"),
    path("api/docs/redoc/", drf_spectacular_views.SpectacularRedocView.as_view(url_name="schema"), name="redoc"),

    # --- Authentication ---
    path("auth/", include("apps.authentication.urls")),

    # --- Dashboard (main UI) ---
    path("", include("apps.dashboard.urls")),

    # --- Other Apps (UI routes) ---
    path("projects/", include("apps.projects.urls")),
    path("extraction/", include("apps.extraction.urls")),
    path("datasets/", include("apps.datasets.urls")),
    path("quality/", include("apps.quality.urls")),
    path("ai/", include("apps.ai_engine.urls")),
    path("exports/", include("apps.exports.urls")),
    path("scheduling/", include("apps.scheduling.urls")),
    path("integrations/", include("apps.integrations.urls")),
    path("knowledge/", include("apps.knowledge_base.urls")),
    path("logs/", include("apps.logs.urls")),
]

# --- Debug toolbar ---
if settings.DEBUG:
    urlpatterns += [
        path("__debug__/", include("debug_toolbar.urls")),
    ]
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# --- Admin site customization ---
admin.site.site_header = "DataExtract AI Administration"
admin.site.site_title = "DataExtract AI Admin"
admin.site.index_title = "Dashboard Administration"
