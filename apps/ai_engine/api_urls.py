"""AI Engine API URL routes."""

from django.urls import path

from .api_views import analyze_page_api, chat_api

urlpatterns = [
    path("ai/analyze/", analyze_page_api, name="api-ai-analyze"),
    path("ai/chat/", chat_api, name="api-ai-chat"),
]
