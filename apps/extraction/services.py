"""
Extraction services — Core extraction pipeline.
"""

import logging
from datetime import datetime
from typing import Optional

from django.utils import timezone

from apps.scraping.services import (
    check_robots_txt,
    extract_with_selector,
    fetch_javascript,
    fetch_static,
    parse_html,
)

logger = logging.getLogger(__name__)


def analyze_page(url: str, render_mode: str = "static") -> dict:
    """
    Analyze a web page: fetch, detect structure, identify repeatable elements.
    Returns analysis report for the UI.
    """
    # Fetch page
    if render_mode == "javascript":
        result = fetch_javascript(url)
    else:
        result = fetch_static(url)

    if not result["success"]:
        return {
            "success": False,
            "error": result["error"],
            "status_code": result.get("status_code", 0),
        }

    html = result["html"]
    soup = parse_html(html)

    # Detect repeatable elements (potential list items)
    repeatable = []
    for tag in ["div", "article", "li", "tr", "section"]:
        elements = soup.find_all(tag, recursive=True)
        class_counts = {}
        for el in elements:
            classes = el.get("class", [])
            if classes:
                key = f"{tag}.{'.'.join(classes)}"
                class_counts[key] = class_counts.get(key, 0) + 1

        for selector, count in class_counts.items():
            if count >= 3:
                repeatable.append({"selector": selector, "count": count})

    repeatable.sort(key=lambda x: x["count"], reverse=True)

    # Detect common field patterns
    detected_fields = _detect_fields(soup)

    return {
        "success": True,
        "url": result.get("url_final", url),
        "status_code": result["status_code"],
        "html_size": len(html),
        "title": soup.title.string.strip() if soup.title and soup.title.string else "",
        "repeatable_elements": repeatable[:20],
        "detected_fields": detected_fields,
        "render_mode": render_mode,
    }


def _detect_fields(soup) -> list[dict]:
    """Detect likely data fields in the HTML."""
    fields = []

    # Common patterns
    patterns = [
        ("Title", "h1, h2.title, .product-title, .item-title"),
        ("Price", ".price, .product-price, [data-price], .amount"),
        ("Description", ".description, .product-description, .item-desc"),
        ("Image", "img.product-image, img[src*='product'], .item-image img"),
        ("Category", ".category, .breadcrumb li:last-child, .tag"),
        ("Rating", ".rating, .stars, [data-rating]"),
    ]

    for name, selector in patterns:
        elements = soup.select(selector)
        if elements:
            fields.append({
                "name": name,
                "selector": selector.split(",")[0].strip(),
                "count": len(elements),
                "example": elements[0].get_text(strip=True)[:100] if elements[0].get_text(strip=True) else elements[0].get("src", "")[:100],
            })

    return fields


def test_extraction(config) -> dict:
    """
    Test an extraction configuration against its target URL.
    Returns test report with extracted sample data.
    """
    from apps.extraction.models import ExtractionConfig

    url = config.target_url
    render_mode = config.render_mode

    # Fetch
    if render_mode == "javascript":
        result = fetch_javascript(url, wait_selector=config.wait_for_selector)
    else:
        result = fetch_static(url)

    if not result["success"]:
        return {
            "success": False,
            "error": result["error"],
            "fields_tested": [],
            "records": [],
        }

    html = result["html"]
    selectors = config.selectors.all().order_by("order")

    # Test each selector
    fields_tested = []
    max_records = 0
    all_extracted = {}

    for sel in selectors:
        values = extract_with_selector(html, sel.selector_value, sel.method, sel.attribute)
        all_extracted[sel.name] = values
        max_records = max(max_records, len(values))

        fields_tested.append({
            "name": sel.name,
            "type": sel.selector_type,
            "method": sel.method,
            "selector": sel.selector_value,
            "count": len(values),
            "required": sel.is_required,
            "valid": len(values) > 0 or not sel.is_required,
            "sample": values[:3] if values else [],
        })

    # Build records
    records = []
    for i in range(min(max_records, 5)):  # Max 5 sample records
        record = {}
        for sel in selectors:
            values = all_extracted.get(sel.name, [])
            record[sel.name] = values[i] if i < len(values) else ""
        records.append(record)

    valid_count = sum(1 for f in fields_tested if f["valid"])
    total = len(fields_tested)

    return {
        "success": True,
        "url": url,
        "html_size": len(html),
        "fields_tested": fields_tested,
        "fields_valid": valid_count,
        "fields_total": total,
        "records": records,
        "total_possible": max_records,
    }


def run_extraction(job) -> dict:
    """
    Execute a full extraction job.
    Returns summary of results.
    """
    from apps.datasets.models import DataField, DataRecord, Dataset
    from apps.extraction.models import ExtractionJob

    config = job.config
    job.status = "RUNNING"
    job.started_at = timezone.now()
    job.save()

    try:
        # Fetch first page
        if config.render_mode == "javascript":
            result = fetch_javascript(config.target_url, wait_selector=config.wait_for_selector)
        else:
            result = fetch_static(config.target_url)

        if not result["success"]:
            job.status = "FAILED"
            job.error_message = result["error"]
            job.completed_at = timezone.now()
            job.save()
            return {"success": False, "error": result["error"]}

        html = result["html"]
        selectors = list(config.selectors.all().order_by("order"))

        # Extract data
        all_extracted = {}
        max_records = 0
        for sel in selectors:
            values = extract_with_selector(html, sel.selector_value, sel.method, sel.attribute)
            all_extracted[sel.name] = values
            max_records = max(max_records, len(values))

        # Create dataset
        dataset = Dataset.objects.create(
            extraction_job=job,
            project=job.project,
            name=f"{config.name} - {timezone.now().strftime('%Y-%m-%d %H:%M')}",
            total_records=max_records,
        )

        # Create field definitions
        for idx, sel in enumerate(selectors):
            DataField.objects.create(
                dataset=dataset,
                name=sel.name,
                field_type=sel.selector_type,
                order=idx,
            )

        # Create records
        valid_count = 0
        invalid_count = 0
        for i in range(max_records):
            data = {}
            missing_required = False
            for sel in selectors:
                values = all_extracted.get(sel.name, [])
                val = values[i] if i < len(values) else ""
                data[sel.name] = val
                if sel.is_required and not val:
                    missing_required = True

            status = DataRecord.ValidationStatus.INVALID if missing_required else DataRecord.ValidationStatus.VALID
            if status == DataRecord.ValidationStatus.VALID:
                valid_count += 1
            else:
                invalid_count += 1

            DataRecord.objects.create(
                dataset=dataset,
                data=data,
                validation_status=status,
                source_url=config.target_url,
            )

        dataset.valid_records = valid_count
        dataset.invalid_records = invalid_count
        dataset.status = "READY"
        dataset.save()

        job.status = "SUCCESS"
        job.rows_extracted = max_records
        job.rows_valid = valid_count
        job.rows_invalid = invalid_count
        job.pages_scraped = 1
        job.completed_at = timezone.now()
        job.result_summary = {"dataset_id": str(dataset.id)}
        job.save()

        return {
            "success": True,
            "dataset_id": str(dataset.id),
            "records": max_records,
            "valid": valid_count,
            "invalid": invalid_count,
        }

    except Exception as e:
        logger.exception(f"Extraction job {job.id} failed")
        job.status = "FAILED"
        job.error_message = str(e)
        job.completed_at = timezone.now()
        job.save()
        return {"success": False, "error": str(e)}
