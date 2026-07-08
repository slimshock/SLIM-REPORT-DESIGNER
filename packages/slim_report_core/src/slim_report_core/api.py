"""Public convenience API for rendering report domain models."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .exceptions import ReportValidationError
from .report import Report
from .schema import normalize_template_mapping


def normalize_template(template: Mapping[str, Any]) -> dict[str, Any]:
    """Return a serializer-ready template mapping without mutating the input."""
    return normalize_template_mapping(template)


def render_html(report: Report, data: Any = None) -> str:
    """Render a report domain model as HTML."""
    return _require_report(report).render_html(data)


def render_pdf(report: Report, data: Any = None) -> bytes:
    """Render a report domain model as PDF bytes."""
    return _require_report(report).render_pdf(data)


def _require_report(report: Report) -> Report:
    if isinstance(report, Report):
        return report
    raise ReportValidationError("Renderer expects a Report domain model.")
