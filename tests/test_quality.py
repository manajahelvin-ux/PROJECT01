"""
Tests for quality services.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.datasets.models import DataField, DataRecord, Dataset
from apps.extraction.models import ExtractionConfig, ExtractionJob
from apps.projects.models import Project
from apps.quality.services import calculate_quality, detect_duplicates

User = get_user_model()


class TestQualityService(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("tester", "test@test.com", "pass1234")
        self.project = Project.objects.create(name="Test", owner=self.user)
        self.config = ExtractionConfig.objects.create(
            project=self.project, name="Test", target_url="https://example.com", created_by=self.user
        )
        self.job = ExtractionJob.objects.create(config=self.config, project=self.project)
        self.dataset = Dataset.objects.create(
            extraction_job=self.job, project=self.project, name="Test DS", total_records=3
        )
        DataField.objects.create(dataset=self.dataset, name="name", field_type="text")
        DataField.objects.create(dataset=self.dataset, name="price", field_type="price")

        DataRecord.objects.create(dataset=self.dataset, data={"name": "Widget", "price": "29.99"}, validation_status="VALID")
        DataRecord.objects.create(dataset=self.dataset, data={"name": "Gadget", "price": "49.99"}, validation_status="VALID")
        DataRecord.objects.create(dataset=self.dataset, data={"name": "", "price": "invalid"}, validation_status="INVALID")

    def test_calculate_quality(self):
        report = calculate_quality(self.dataset)
        self.assertGreater(report.global_score, 0)
        self.assertGreater(report.completeness, 0)

    def test_detect_duplicates(self):
        # Add a duplicate
        DataRecord.objects.create(dataset=self.dataset, data={"name": "Widget", "price": "29.99"})
        dupes = detect_duplicates(self.dataset)
        self.assertGreater(dupes, 0)
