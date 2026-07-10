"""Validation helpers for the public report template shape."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .exceptions import ReportValidationError
from .utils import ensure_list, ensure_mapping

REPORT_TEMPLATE_KEYS = (
    "version",
    "metadata",
    "page",
    "objects",
    "bands",
    "assets",
)

_BAND_TYPE_ALIASES = {
    "pageHeader": "page_header",
    "page-header": "page_header",
    "page_header": "page_header",
    "pageFooter": "page_footer",
    "page-footer": "page_footer",
    "page_footer": "page_footer",
    "groupHeader": "group_header",
    "group-header": "group_header",
    "group_header": "group_header",
    "groupFooter": "group_footer",
    "group-footer": "group_footer",
    "group_footer": "group_footer",
    "detail": "detail",
}


def normalize_template_mapping(data: Mapping[str, Any]) -> dict[str, Any]:
    """Return a serializer-ready copy of a report template mapping."""
    normalized = dict(data)
    metadata = dict(normalized.get("metadata") or {})
    if "title" not in metadata and metadata.get("name"):
        metadata["title"] = metadata["name"]
    if "name" not in metadata and metadata.get("title"):
        metadata["name"] = metadata["title"]
    if "custom" not in metadata and metadata.get("template_id"):
        metadata["custom"] = {"id": str(metadata["template_id"])}

    normalized["metadata"] = metadata
    normalized.setdefault("version", "0.1")
    normalized.setdefault("page", {"size": "A4", "orientation": "portrait"})
    normalized["page"] = dict(normalized["page"])
    normalized["page"].setdefault("unit", "px")
    normalized.setdefault("bands", [])
    if isinstance(normalized["bands"], list):
        normalized["bands"] = [_normalize_band_mapping(item) for item in normalized["bands"]]
    normalized.setdefault("objects", [])
    if isinstance(normalized["objects"], list):
        if normalized["objects"]:
            normalized["objects"] = [
                dict(item) if isinstance(item, Mapping) else item for item in normalized["objects"]
            ]
        else:
            normalized["objects"] = _flatten_band_objects(normalized["bands"])
    normalized.setdefault("assets", [])
    normalized.setdefault("dataSources", [])
    normalized.setdefault("datasets", [])
    return normalized


def _normalize_band_mapping(value: Any) -> Any:
    if not isinstance(value, Mapping):
        return value
    normalized = dict(value)
    band_type = normalized.get("type")
    if isinstance(band_type, str):
        normalized["type"] = _BAND_TYPE_ALIASES.get(band_type, band_type)
    return normalized


def _flatten_band_objects(bands: Any) -> list[Any]:
    if not isinstance(bands, list):
        return []
    objects: list[Any] = []
    for band in bands:
        if not isinstance(band, Mapping):
            continue
        band_objects = band.get("objects")
        if not isinstance(band_objects, list):
            continue
        band_id = str(band.get("id") or "").strip()
        for item in band_objects:
            if not isinstance(item, Mapping):
                objects.append(item)
                continue
            normalized_object = dict(item)
            if band_id:
                _assign_object_band(normalized_object, band_id)
            objects.append(normalized_object)
    return objects


def _assign_object_band(report_object: dict[str, Any], band_id: str) -> None:
    original_band = report_object.get(
        "band",
        report_object.get("band_id", report_object.get("bandId")),
    )
    if original_band not in (None, "", band_id):
        properties = report_object.get("properties")
        if isinstance(properties, Mapping):
            properties = dict(properties)
        else:
            properties = {}
        properties.setdefault("_slim_original_band", original_band)
        report_object["properties"] = properties
    report_object["band"] = band_id
    report_object["band_id"] = band_id


def validate_template_mapping(data: Mapping[str, Any]) -> None:
    """Validate that data has the minimum report template structure."""
    missing_keys = [key for key in REPORT_TEMPLATE_KEYS if key not in data]
    if missing_keys:
        joined = ", ".join(missing_keys)
        raise ReportValidationError(f"Report template is missing required keys: {joined}.")

    if not isinstance(data["version"], str) or not data["version"].strip():
        raise ReportValidationError("Report template version must be a non-empty string.")

    ensure_mapping(data["metadata"], context="Report metadata")
    ensure_mapping(data["page"], context="Report page")
    ensure_list(data["objects"], context="Report objects")
    ensure_list(data["bands"], context="Report bands")
    ensure_list(data["assets"], context="Report assets")
