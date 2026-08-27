"""Datasets URL routes."""

from django.urls import path

from . import views

app_name = "datasets"

urlpatterns = [
    path("", views.dataset_list, name="list"),
    path("<uuid:pk>/", views.dataset_detail, name="detail"),
    path("<uuid:pk>/quality/", views.run_quality, name="quality"),
    path("<uuid:pk>/export/", views.export_dataset_view, name="export"),
    path("<uuid:pk>/record/<uuid:record_id>/validate/", views.validate_record, name="validate_record"),
]
