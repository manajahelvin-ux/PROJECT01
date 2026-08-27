"""Extraction URL routes."""

from django.urls import path

from . import views

app_name = "extraction"

urlpatterns = [
    path("", views.extraction_list, name="list"),
    path("create/", views.create_extraction, name="create"),
    path("<uuid:pk>/", views.extraction_detail, name="detail"),
    path("<uuid:pk>/test/", views.test_extraction_view, name="test"),
    path("<uuid:pk>/run/", views.run_extraction_view, name="run"),
    path("analyze/", views.analyze_page_view, name="analyze"),
]
