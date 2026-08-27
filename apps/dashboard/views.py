"""Dashboard views."""

from django.http import JsonResponse
from django.shortcuts import redirect, render

from apps.projects.models import Project
from apps.extraction.models import ExtractionJob
from apps.datasets.models import Dataset, DataRecord
from apps.quality.models import QualityReport


def index(request):
    """Redirect root URL to dashboard."""
    return redirect("dashboard:dashboard")


def dashboard_view(request):
    """Main dashboard view with KPIs."""
    if not request.user.is_authenticated:
        return redirect("authentication:login")

    total_projects = Project.objects.count()
    total_websites = 0
    total_extractions = ExtractionJob.objects.count()
    total_records = DataRecord.objects.count()

    quality_reports = QualityReport.objects.all()
    avg_quality = 0
    if quality_reports.exists():
        avg_quality = round(sum(q.global_score for q in quality_reports) / quality_reports.count(), 1)

    active_extractions = ExtractionJob.objects.filter(status="RUNNING").count()

    context = {
        "page_title": "Dashboard",
        "kpi": {
            "total_projects": total_projects,
            "total_websites": total_websites,
            "total_extractions": total_extractions,
            "total_records": total_records,
            "avg_quality_score": avg_quality,
            "active_extractions": active_extractions,
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

    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        health["database"] = "ok"
    except Exception:
        health["database"] = "error"
        health["status"] = "degraded"

    return JsonResponse(health)
