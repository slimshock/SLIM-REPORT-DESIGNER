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

