"""
Export services — Generate export files in multiple formats.
"""

import csv
import io
import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime

from django.conf import settings


def export_dataset(dataset, format_type: str, valid_only: bool = False) -> dict:
    """
    Export a dataset to the specified format.
    Returns: {success, file_path, file_size, records_count}
    """
    records = dataset.records.all()
    if valid_only:
        records = records.filter(validation_status="VALID")

    records = list(records)
    if not records:
        return {"success": False, "error": "Aucun enregistrement à exporter"}

    # Get field names from first record
    field_names = list(records[0].data.keys()) if records else []

    # Create export directory
    export_dir = settings.MEDIA_ROOT / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"{dataset.name}_{timestamp}".replace(" ", "_").replace("/", "-")

    try:
        if format_type == "csv":
            return _export_csv(records, field_names, export_dir, base_name)
        elif format_type == "xlsx":
            return _export_xlsx(records, field_names, export_dir, base_name)
        elif format_type == "json":
            return _export_json(records, export_dir, base_name)
        elif format_type == "xml":
            return _export_xml(records, field_names, export_dir, base_name)
        elif format_type == "parquet":
            return _export_parquet(records, field_names, export_dir, base_name)
        else:
            return {"success": False, "error": f"Format non supporté: {format_type}"}

    except Exception as e:
        return {"success": False, "error": str(e)}


def _export_csv(records, field_names, export_dir, base_name):
    file_path = export_dir / f"{base_name}.csv"
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=field_names)
        writer.writeheader()
        for record in records:
            writer.writerow(record.data)
    size = os.path.getsize(file_path)
    return {"success": True, "file_path": str(file_path), "file_size": size, "records_count": len(records)}


def _export_xlsx(records, field_names, export_dir, base_name):
    import pandas as pd
    file_path = export_dir / f"{base_name}.xlsx"
    data = [r.data for r in records]
    df = pd.DataFrame(data, columns=field_names)
    df.to_excel(file_path, index=False, engine="openpyxl")
    size = os.path.getsize(file_path)
    return {"success": True, "file_path": str(file_path), "file_size": size, "records_count": len(records)}


def _export_json(records, export_dir, base_name):
    file_path = export_dir / f"{base_name}.json"
    data = [r.data for r in records]
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    size = os.path.getsize(file_path)
    return {"success": True, "file_path": str(file_path), "file_size": size, "records_count": len(records)}


def _export_xml(records, field_names, export_dir, base_name):
    file_path = export_dir / f"{base_name}.xml"
    root = ET.Element("dataset")
    for record in records:
        item = ET.SubElement(root, "record")
        for key, value in record.data.items():
            field = ET.SubElement(item, key)
            field.text = str(value) if value else ""
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(file_path, encoding="utf-8", xml_declaration=True)
    size = os.path.getsize(file_path)
    return {"success": True, "file_path": str(file_path), "file_size": size, "records_count": len(records)}


def _export_parquet(records, field_names, export_dir, base_name):
    import pandas as pd
    file_path = export_dir / f"{base_name}.parquet"
    data = [r.data for r in records]
    df = pd.DataFrame(data, columns=field_names)
    df.to_parquet(file_path, engine="pyarrow", index=False)
    size = os.path.getsize(file_path)
    return {"success": True, "file_path": str(file_path), "file_size": size, "records_count": len(records)}
