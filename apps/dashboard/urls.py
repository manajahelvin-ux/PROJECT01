"""Dashboard URL routes."""

from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.index, name="index"),
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("download/", views.download_zip, name="download"),
]
