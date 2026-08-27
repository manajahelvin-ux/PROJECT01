"""Extraction views."""

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .models import ExtractionConfig, ExtractionJob, Selector
from .services import analyze_page, run_extraction, test_extraction


@login_required
def extraction_list(request):
    configs = ExtractionConfig.objects.filter(
        models.Q(project__owner=request.user) | models.Q(project__members=request.user)
    ).distinct().order_by("-updated_at")
    return render(request, "extraction/list.html", {"configs": configs})


@login_required
def create_extraction(request):
    from apps.projects.models import Project

    projects = Project.objects.filter(owner=request.user)

    if request.method == "POST":
        project_id = request.POST.get("project")
        name = request.POST.get("name", "")
        target_url = request.POST.get("target_url", "")
        render_mode = request.POST.get("render_mode", "static")
        wait_selector = request.POST.get("wait_for_selector", "")
        max_pages = int(request.POST.get("max_pages", 1))

        project = get_object_or_404(Project, id=project_id, owner=request.user)

        config = ExtractionConfig.objects.create(
            project=project,
            name=name,
            target_url=target_url,
            render_mode=render_mode,
            wait_for_selector=wait_selector,
            max_pages=max_pages,
            created_by=request.user,
        )

        # Parse selectors from JSON
        selectors_json = request.POST.get("selectors_json", "[]")
        try:
            selectors_data = json.loads(selectors_json)
            for idx, s in enumerate(selectors_data):
                Selector.objects.create(
                    config=config,
                    name=s.get("name", ""),
                    selector_type=s.get("type", "text"),
                    method=s.get("method", "css"),
                    selector_value=s.get("selector", ""),
                    is_required=s.get("required", False),
                    attribute=s.get("attribute", ""),
                    order=idx,
                )
        except (json.JSONDecodeError, TypeError):
            pass

        messages.success(request, f"Extraction '{name}' créée avec succès.")
        return redirect("extraction:detail", pk=config.id)

    return render(request, "extraction/create.html", {"projects": projects})


@login_required
def extraction_detail(request, pk):
    config = get_object_or_404(ExtractionConfig, pk=pk)
    jobs = config.jobs.all()[:10]
    versions = config.versions.all()[:10]
    return render(request, "extraction/detail.html", {
        "config": config,
        "jobs": jobs,
        "versions": versions,
        "selectors": config.selectors.all(),
    })


@login_required
def test_extraction_view(request, pk):
    config = get_object_or_404(ExtractionConfig, pk=pk)
    result = test_extraction(config)
    if request.headers.get("Accept") == "application/json":
        return JsonResponse(result)
    return render(request, "extraction/test_result.html", {"config": config, "result": result})


@login_required
def run_extraction_view(request, pk):
    config = get_object_or_404(ExtractionConfig, pk=pk)
    job = ExtractionJob.objects.create(
        config=config,
        project=config.project,
        created_by=request.user,
    )
    result = run_extraction(job)
    messages.success(request, f"Extraction terminée: {result.get('records', 0)} lignes extraites.")
    return redirect("extraction:detail", pk=config.id)


@login_required
def analyze_page_view(request):
    if request.method == "POST":
        url = request.POST.get("url", "")
        render_mode = request.POST.get("render_mode", "static")
        result = analyze_page(url, render_mode)
        return JsonResponse(result)
    return render(request, "extraction/analyze.html")
