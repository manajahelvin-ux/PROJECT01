"""
Management command: seed_demo
Creates demo data for testing and demonstration.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.ai_engine.models import AIRequest, AIResponse
from apps.datasets.models import DataField, DataRecord, Dataset
from apps.extraction.models import ExtractionConfig, ExtractionConfigVersion, ExtractionJob, Selector
from apps.integrations.models import Webhook
from apps.knowledge_base.models import KnowledgeArticle
from apps.logs.models import ActivityLog, Notification
from apps.projects.models import Project
from apps.quality.models import Anomaly, QualityReport
from apps.scraping.models import Website
from apps.scheduling.models import ScheduledJob

User = get_user_model()


class Command(BaseCommand):
    help = "Seed the database with demo data for testing and demonstration."

    def handle(self, *args, **options):
        self.stdout.write("🌱 Creating demo data...")

        # Create demo user
        user, created = User.objects.get_or_create(
            username="demo",
            defaults={
                "email": "demo@dataextract.ai",
                "role": "ADMIN",
                "is_staff": True,
            },
        )
        if created:
            user.set_password("demo1234")
            user.save()
            self.stdout.write("  ✅ Demo user created (demo / demo1234)")
        else:
            self.stdout.write("  ℹ️  Demo user already exists")

        # Create demo project
        project, _ = Project.objects.get_or_create(
            name="Demo E-commerce",
            defaults={
                "description": "Projet de démonstration — Extraction de produits depuis un site e-commerce.",
                "category": "ECOMMERCE",
                "status": "ACTIVE",
                "owner": user,
            },
        )
        self.stdout.write(f"  ✅ Project: {project.name}")

        # Create website
        website, _ = Website.objects.get_or_create(
            name="Example Products",
            defaults={
                "project": project,
                "base_url": "https://example.com/products",
                "crawl_delay": 2.0,
            },
        )
        self.stdout.write(f"  ✅ Website: {website.name}")

        # Create extraction config
        config, config_created = ExtractionConfig.objects.get_or_create(
            name="Products Extraction",
            defaults={
                "project": project,
                "website": website,
                "target_url": "https://example.com/products",
                "render_mode": "static",
                "created_by": user,
            },
        )

        if config_created:
            # Create version 1
            ExtractionConfigVersion.objects.create(
                config=config,
                version_number=1,
                snapshot={"selectors": [], "url": config.target_url},
                changed_by=user,
                change_note="Initial configuration",
            )

            # Create selectors
            selectors_data = [
                ("product_name", "text", "css", "h2.product-title", True),
                ("price", "price", "css", ".price", True),
                ("description", "text", "css", ".description", False),
                ("image_url", "image", "css", "img.product-image", False),
                ("category", "text", "css", ".category", False),
            ]
            for idx, (name, stype, method, selector, required) in enumerate(selectors_data):
                Selector.objects.create(
                    config=config,
                    name=name,
                    selector_type=stype,
                    method=method,
                    selector_value=selector,
                    is_required=required,
                    order=idx,
                )
            self.stdout.write(f"  ✅ Extraction config: {config.name} ({len(selectors_data)} selectors)")

        # Create demo extraction job
        job, _ = ExtractionJob.objects.get_or_create(
            config=config,
            project=project,
            defaults={
                "status": "SUCCESS",
                "pages_scraped": 1,
                "rows_extracted": 10,
                "rows_valid": 8,
                "rows_invalid": 2,
                "created_by": user,
            },
        )
        self.stdout.write(f"  ✅ Extraction job: {job.status}")

        # Create demo dataset
        dataset, ds_created = Dataset.objects.get_or_create(
            extraction_job=job,
            defaults={
                "project": project,
                "name": "Demo Products Dataset",
                "status": "READY",
                "total_records": 10,
                "valid_records": 8,
                "invalid_records": 2,
            },
        )

        if ds_created:
            # Create fields
            fields = []
            for idx, (name, stype) in enumerate([("product_name", "text"), ("price", "price"), ("description", "text"), ("image_url", "image"), ("category", "text")]):
                fields.append(DataField.objects.create(dataset=dataset, name=name, field_type=stype, order=idx))

            # Create demo records
            demo_products = [
                {"product_name": "Laptop Pro 15", "price": "€1,299.99", "description": "High-performance laptop", "image_url": "https://example.com/img/laptop.jpg", "category": "Electronics"},
                {"product_name": "Wireless Mouse", "price": "€29.99", "description": "Ergonomic wireless mouse", "image_url": "https://example.com/img/mouse.jpg", "category": "Accessories"},
                {"product_name": "USB-C Hub", "price": "€49.99", "description": "7-in-1 hub", "image_url": "https://example.com/img/hub.jpg", "category": "Accessories"},
                {"product_name": "Mechanical Keyboard", "price": "€89.99", "description": "RGB mechanical keyboard", "image_url": "", "category": "Accessories"},
                {"product_name": "", "price": "€199.99", "description": "Unknown product", "image_url": "", "category": ""},
            ]
            for i, data in enumerate(demo_products):
                status = DataRecord.ValidationStatus.VALID if data["product_name"] else DataRecord.ValidationStatus.INVALID
                DataRecord.objects.create(
                    dataset=dataset,
                    data=data,
                    validation_status=status,
                    quality_score=95 if status == "VALID" else 45,
                    source_url="https://example.com/products",
                )

            self.stdout.write(f"  ✅ Dataset: {dataset.name} ({dataset.total_records} records)")

        # Quality report
        QualityReport.objects.get_or_create(
            dataset=dataset,
            defaults={
                "completeness": 82.0,
                "accuracy": 88.0,
                "consistency": 90.0,
                "uniqueness": 95.0,
                "validity": 80.0,
            },
        )
        self.stdout.write("  ✅ Quality report created")

        # Scheduled job
        ScheduledJob.objects.get_or_create(
            name="Daily Products Sync",
            defaults={
                "config": config,
                "frequency": "daily",
                "is_active": True,
                "created_by": user,
            },
        )
        self.stdout.write("  ✅ Scheduled job created")

        # Webhook
        Webhook.objects.get_or_create(
            name="Demo Webhook",
            defaults={
                "project": project,
                "url": "https://httpbin.org/post",
                "is_active": True,
                "created_by": user,
            },
        )
        self.stdout.write("  ✅ Webhook created")

        # Knowledge articles
        KnowledgeArticle.objects.get_or_create(
            title="Guide: Extraction e-commerce",
            defaults={
                "content": "## Conseils pour l'extraction e-commerce\n\n1. Toujours vérifier les prix avec des sélecteurs `.price`\n2. Attention aux images lazy-loaded\n3. Respecter le robots.txt",
                "category": "ECOMMERCE",
                "author": user,
                "tags": ["ecommerce", "products", "price"],
            },
        )
        self.stdout.write("  ✅ Knowledge article created")

        # Activity logs
        ActivityLog.objects.get_or_create(
            action="seed_demo",
            user=user,
            project=project,
            defaults={
                "description": "Demo data seeded successfully",
                "level": "INFO",
            },
        )

        # Notification
        Notification.objects.get_or_create(
            user=user,
            title="Demo data loaded",
            defaults={
                "notification_type": "extraction_complete",
                "message": "Les données de démonstration ont été chargées avec succès.",
            },
        )

        self.stdout.write(self.style.SUCCESS("\n✅ Demo data created successfully!"))
        self.stdout.write(self.style.SUCCESS("   Login: demo / demo1234"))
