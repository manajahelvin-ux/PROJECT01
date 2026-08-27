"""Dataset views."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.exports.services import export_dataset
from apps.quality.services import calculate_quality, detect_anomalies_statistical, detect_duplicates

from .models import DataRecord, Dataset


@login_required
def dataset_list(request):
    from django.db import models
    datasets = Dataset.objects.filter(
        models.Q(project__owner=request.user) | models.Q(project__members=request.user)
    ).distinct().order_by("-created_at")
    return render(request, "datasets/list.html", {"datasets": datasets})


@login_required
def dataset_detail(request, pk):
    dataset = get_object_or_404(Dataset, pk=pk)
    records = dataset.records.all()

    # Filtering
    status_filter = request.GET.get("status", "")
    if status_filter:
        records = records.filter(validation_status=status_filter)

    search = request.GET.get("q", "")
    if search:
        records = records.filter(data__icontains=search)

    # Pagination
    page = int(request.GET.get("page", 1))
    per_page = 25
    total = records.count()
    records_page = records[(page - 1) * per_page: page * per_page]
    total_pages = (total + per_page - 1) // per_page

    fields = list(dataset.fields.all())

    return render(request, "datasets/detail.html", {
        "dataset": dataset,
        "records": records_page,
        "fields": fields,
        "status_filter": status_filter,
        "search": search,
        "page": page,
        "total_pages": total_pages,
        "total": total,
    })


@login_required
def run_quality(request, pk):
    dataset = get_object_or_404(Dataset, pk=pk)
    report = calculate_quality(dataset)
    dupes = detect_duplicates(dataset)
    anomalies = detect_anomalies_statistical(dataset)
    messages.success(request, f"Analyse qualité terminée. Score: {report.global_score}/100. {len(anomalies)} anomalies, {dupes} doublons.")
    return redirect("datasets:detail", pk=pk)


@login_required
def export_dataset_view(request, pk):
    dataset = get_object_or_404(Dataset, pk=pk)
    format_type = request.POST.get("format", "csv")
    valid_only = request.POST.get("valid_only") == "on"
    result = export_dataset(dataset, format_type, valid_only)
    if result["success"]:
        messages.success(request, f"Export {format_type.upper()} généré ({result['records_count']} lignes).")
    else:
        messages.error(request, f"Erreur export: {result.get('error')}")
    return redirect("datasets:detail", pk=pk)


@login_required
def validate_record(request, pk, record_id):
    dataset = get_object_or_404(Dataset, pk=pk)
    record = get_object_or_404(DataRecord, pk=record_id, dataset=dataset)
    new_status = request.POST.get("status", "VALID")
    record.validation_status = new_status
    record.save()
    return redirect("datasets:detail", pk=pk)
