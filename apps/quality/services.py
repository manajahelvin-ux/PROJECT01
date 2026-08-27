"""
Quality services — Data quality scoring and anomaly detection.
"""

import re
from collections import Counter

from django.utils import timezone

from .models import Anomaly, QualityReport


def calculate_quality(dataset) -> QualityReport:
    """Calculate data quality scores for a dataset."""
    records = list(dataset.records.all())
    total = len(records)

    if total == 0:
        report, _ = QualityReport.objects.get_or_create(dataset=dataset)
        report.completeness = 0
        report.accuracy = 0
        report.consistency = 0
        report.uniqueness = 0
        report.validity = 0
        report.save()
        return report

    fields = list(dataset.fields.all())
    field_names = [f.name for f in fields]

    # --- Completeness: % of non-empty fields across all records ---
    total_fields = total * len(field_names) if field_names else 1
    filled_fields = 0
    for record in records:
        data = record.data or {}
        for fname in field_names:
            val = data.get(fname, "")
            if val and str(val).strip():
                filled_fields += 1
    completeness = round((filled_fields / total_fields) * 100, 1) if total_fields else 0

    # --- Accuracy: % of records with valid format values ---
    valid_format_count = 0
    total_checked = 0
    for record in records:
        data = record.data or {}
        record_valid = True
        for field in fields:
            val = str(data.get(field.name, "")).strip()
            if not val:
                continue
            total_checked += 1
            if field.field_type == "email" and not _is_valid_email(val):
                record_valid = False
            elif field.field_type == "url" and not _is_valid_url(val):
                record_valid = False
            elif field.field_type == "price" and not _is_valid_price(val):
                record_valid = False
        if record_valid:
            valid_format_count += 1
    accuracy = round((valid_format_count / total) * 100, 1) if total else 0

    # --- Consistency: format uniformity ---
    consistency_scores = []
    for field in fields:
        values = [str(r.data.get(field.name, "")).strip() for r in records if r.data.get(field.name)]
        if not values:
            continue
        formats = Counter(_detect_format(v) for v in values)
        dominant_count = formats.most_common(1)[0][1] if formats else 0
        consistency_scores.append(dominant_count / len(values) * 100)
    consistency = round(sum(consistency_scores) / len(consistency_scores), 1) if consistency_scores else 100

    # --- Uniqueness: % of unique records ---
    seen = set()
    unique_count = 0
    for record in records:
        key = str(sorted((record.data or {}).items()))
        if key not in seen:
            seen.add(key)
            unique_count += 1
    uniqueness = round((unique_count / total) * 100, 1) if total else 100

    # --- Validity: % of records passing validation status ---
    valid_records = sum(1 for r in records if r.validation_status == "VALID")
    validity = round((valid_records / total) * 100, 1) if total else 0

    # Save report
    report, _ = QualityReport.objects.get_or_create(dataset=dataset)
    report.completeness = completeness
    report.accuracy = accuracy
    report.consistency = consistency
    report.uniqueness = uniqueness
    report.validity = validity
    report.save()

    # Update dataset
    dataset.avg_quality_score = report.global_score
    dataset.save()

    return report


def detect_duplicates(dataset) -> int:
    """Detect and mark duplicate records in a dataset."""
    records = list(dataset.records.all())
    seen = {}
    duplicate_count = 0

    for record in records:
        key = str(sorted((record.data or {}).items()))
        if key in seen:
            record.is_duplicate = True
            record.duplicate_of = seen[key]
            record.save()
            duplicate_count += 1
        else:
            seen[key] = record

    dataset.duplicate_count = duplicate_count
    dataset.save()
    return duplicate_count


def detect_anomalies_statistical(dataset) -> list:
    """Detect anomalies using statistical methods."""
    records = list(dataset.records.all())
    fields = list(dataset.fields.all())
    anomalies = []

    for field in fields:
        values = []
        for r in records:
            val = r.data.get(field.name, "")
            if val and str(val).strip():
                values.append((r, str(val).strip()))

        if field.field_type == "price":
            numeric = []
            for record, val in values:
                num = _extract_number(val)
                if num is not None:
                    numeric.append((record, num))

            if len(numeric) >= 3:
                nums = [n for _, n in numeric]
                mean = sum(nums) / len(nums)
                std = (sum((x - mean) ** 2 for x in nums) / len(nums)) ** 0.5
                if std > 0:
                    for record, num in numeric:
                        z_score = abs(num - mean) / std
                        if z_score > 3:
                            anomalies.append(Anomaly(
                                dataset=dataset,
                                record=record,
                                anomaly_type=Anomaly.AnomalyType.OUTLIER,
                                severity=Anomaly.Severity.HIGH,
                                field_name=field.name,
                                description=f"Valeur {num} est un outlier (z-score: {z_score:.1f})",
                            ))

        # Check for empty required fields
        for record, val in values:
            if not val:
                anomalies.append(Anomaly(
                    dataset=dataset,
                    record=record,
                    anomaly_type=Anomaly.AnomalyType.MISSING_VALUE,
                    severity=Anomaly.Severity.MEDIUM,
                    field_name=field.name,
                    description="Valeur manquante",
                ))

        # Validate formats
        for record, val in values:
            if field.field_type == "email" and not _is_valid_email(val):
                anomalies.append(Anomaly(
                    dataset=dataset,
                    record=record,
                    anomaly_type=Anomaly.AnomalyType.INVALID_EMAIL,
                    severity=Anomaly.Severity.MEDIUM,
                    field_name=field.name,
                    description=f"Email invalide: {val[:50]}",
                ))
            elif field.field_type == "url" and not _is_valid_url(val):
                anomalies.append(Anomaly(
                    dataset=dataset,
                    record=record,
                    anomaly_type=Anomaly.AnomalyType.INVALID_URL,
                    severity=Anomaly.Severity.LOW,
                    field_name=field.name,
                    description=f"URL invalide: {val[:50]}",
                ))

    # Bulk create
    if anomalies:
        Anomaly.objects.bulk_create(anomalies)

    return anomalies


# --- Helpers ---

def _is_valid_email(val):
    return bool(re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", val))


def _is_valid_url(val):
    return bool(re.match(r"^https?://[^\s/$.?#].[^\s]*$", val, re.IGNORECASE))


def _is_valid_price(val):
    cleaned = re.sub(r"[^\d.,]", "", val)
    return bool(cleaned)


def _extract_number(val):
    try:
        cleaned = re.sub(r"[^\d.,]", "", val)
        cleaned = cleaned.replace(",", ".")
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def _detect_format(val):
    if re.match(r"^\d{4}-\d{2}-\d{2}", val):
        return "iso_date"
    if re.match(r"^\d{2}/\d{2}/\d{4}", val):
        return "eu_date"
    if re.match(r"^[\d.,]+\s*[€$£]?", val):
        return "number"
    if re.match(r"^https?://", val):
        return "url"
    return "text"
