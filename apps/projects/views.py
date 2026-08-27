"""Projects views."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .models import Project


@login_required
def project_list(request):
    from django.db import models
    projects = Project.objects.filter(
        models.Q(owner=request.user) | models.Q(project_members__user=request.user)
    ).distinct().order_by("-updated_at")
    return render(request, "projects/list.html", {"projects": projects})


@login_required
def project_create(request):
    if request.method == "POST":
        name = request.POST.get("name", "")
        description = request.POST.get("description", "")
        category = request.POST.get("category", "OTHER")
        Project.objects.create(name=name, description=description, category=category, owner=request.user)
        messages.success(request, f"Projet '{name}' créé.")
        return redirect("projects:list")
    return render(request, "projects/create.html", {"categories": Project.Category.choices})


@login_required
def project_detail(request, pk):
    project = get_object_or_404(Project, pk=pk)
    return render(request, "projects/detail.html", {"project": project})
