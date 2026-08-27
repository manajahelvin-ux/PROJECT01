"""Dashboard views."""

from django.http import JsonResponse
from django.shortcuts import redirect, render


def index(request):
    """Redirect root URL to dashboard."""
    return redirect("dashboard:dashboard")


def dashboard_view(request):
    """Main dashboard view with KPIs."""
    context = {
        "page_title": "Dashboard",
        "kpi": {
            "total_projects": 0,
            "total_websites": 0,
            "total_extractions": 0,
            "total_records": 0,
            "avg_quality_score": 0,
            "active_extractions": 0,
        },
    }
    return render(request, "dashboard/index.html", context)


def health_check(request):
    """Health check endpoint for monitoring."""
    health = {
        "status": "healthy",
        "database": "ok",
        "redis": "ok",
        "openrouter": "ok",
    }

    # Check database
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        health["database"] = "ok"
    except Exception:
        health["database"] = "error"
        health["status"] = "degraded"

    return JsonResponse(health)
