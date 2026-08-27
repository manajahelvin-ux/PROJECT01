"""
Tests for API endpoints.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.projects.models import Project

User = get_user_model()


class TestProjectAPI(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user("apiuser", "api@test.com", "pass1234", role="ADMIN")
        self.client.force_authenticate(user=self.user)
        self.project = Project.objects.create(name="API Test", owner=self.user)

    def test_list_projects(self):
        resp = self.client.get("/api/projects/")
        self.assertEqual(resp.status_code, 200)

    def test_create_project(self):
        resp = self.client.post("/api/projects/", {"name": "New Project", "category": "NEWS"})
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["name"], "New Project")

    def test_unauthenticated_blocked(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get("/api/projects/")
        self.assertEqual(resp.status_code, 403)


class TestHealthEndpoint(TestCase):
    def test_health_check(self):
        client = APIClient()
        resp = client.get("/health/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "healthy")
