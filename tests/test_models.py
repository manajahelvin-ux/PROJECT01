"""
Tests for models — basic creation and relationships.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.projects.models import Project
from apps.extraction.models import ExtractionConfig, Selector
from apps.datasets.models import Dataset, DataRecord
from apps.quality.models import QualityReport

User = get_user_model()


class TestUserModel(TestCase):
    def test_create_user_with_role(self):
        user = User.objects.create_user("testuser", "test@test.com", "pass1234", role="OPERATOR")
        self.assertEqual(user.role, "OPERATOR")
        self.assertTrue(user.is_operator)
        self.assertFalse(user.is_admin)

    def test_str_representation(self):
        user = User.objects.create_user("testuser", "test@test.com", "pass1234", role="ADMIN")
        self.assertIn("Administrator", str(user))


class TestProjectModel(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("owner", "owner@test.com", "pass1234")

    def test_create_project(self):
        project = Project.objects.create(name="Test Project", owner=self.user, category="ECOMMERCE")
        self.assertEqual(project.status, "DRAFT")
        self.assertEqual(str(project), "Test Project")


class TestExtractionConfig(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("owner", "owner@test.com", "pass1234")
        self.project = Project.objects.create(name="Test", owner=self.user)

    def test_create_config_with_selectors(self):
        config = ExtractionConfig.objects.create(
            project=self.project,
            name="Test Extraction",
            target_url="https://example.com",
            created_by=self.user,
        )
        Selector.objects.create(config=config, name="title", selector_value="h1.title")
        Selector.objects.create(config=config, name="price", selector_value=".price", selector_type="price")

        self.assertEqual(config.selectors.count(), 2)
        self.assertEqual(config.current_version, 1)


class TestQualityReport(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("owner", "owner@test.com", "pass1234")
        self.project = Project.objects.create(name="Test", owner=self.user)
        self.config = ExtractionConfig.objects.create(
            project=self.project, name="Test", target_url="https://example.com", created_by=self.user
        )
        from apps.extraction.models import ExtractionJob
        self.job = ExtractionJob.objects.create(config=self.config, project=self.project, created_by=self.user)
        self.dataset = Dataset.objects.create(extraction_job=self.job, project=self.project, name="Test DS")

    def test_quality_score_calculation(self):
        report = QualityReport.objects.create(
            dataset=self.dataset,
            completeness=80.0,
            accuracy=90.0,
            consistency=85.0,
            uniqueness=95.0,
            validity=88.0,
        )
        # Global score should be calculated
        self.assertGreater(report.global_score, 0)
        self.assertLess(report.global_score, 100)
