"""
Tests for export services.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.datasets.models import DataField, DataRecord, Dataset
from apps.extraction.models import ExtractionConfig, ExtractionJob
from apps.exports.services import export_dataset
from apps.projects.models import Project

User = get_user_model()


class TestExportService(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("tester", "test@test.com", "pass1234")
        self.project = Project.objects.create(name="Test", owner=self.user)
        self.config = ExtractionConfig.objects.create(
            project=self.project, name="Test", target_url="https://example.com", created_by=self.user
        )
        self.job = ExtractionJob.objects.create(config=self.config, project=self.project)
        self.dataset = Dataset.objects.create(extraction_job=self.job, project=self.project, name="Test DS")
        DataField.objects.create(dataset=self.dataset, name="name", field_type="text")
        DataRecord.objects.create(dataset=self.dataset, data={"name": "Product A"})
        DataRecord.objects.create(dataset=self.dataset, data={"name": "Product B"})

    def test_export_csv(self):
        result = export_dataset(self.dataset, "csv")
        self.assertTrue(result["success"])
        self.assertEqual(result["records_count"], 2)
        self.assertTrue(result["file_path"].endswith(".csv"))

    def test_export_json(self):
        result = export_dataset(self.dataset, "json")
        self.assertTrue(result["success"])
        self.assertTrue(result["file_path"].endswith(".json"))

    def test_export_xlsx(self):
        result = export_dataset(self.dataset, "xlsx")
        self.assertTrue(result["success"])
        self.assertTrue(result["file_path"].endswith(".xlsx"))

    def test_export_xml(self):
        result = export_dataset(self.dataset, "xml")
        self.assertTrue(result["success"])
        self.assertTrue(result["file_path"].endswith(".xml"))

    def test_export_parquet(self):
        result = export_dataset(self.dataset, "parquet")
        self.assertTrue(result["success"])
        self.assertTrue(result["file_path"].endswith(".parquet"))

    def test_export_valid_only(self):
        DataRecord.objects.create(dataset=self.dataset, data={"name": "Bad"}, validation_status="INVALID")
        result = export_dataset(self.dataset, "csv", valid_only=True)
        self.assertTrue(result["success"])
        self.assertEqual(result["records_count"], 2)  # Only VALID records
