"""PDF report exporter backed by ReportLab."""

from __future__ import annotations

from typing import Any

from ..exceptions import ExporterError, ReportValidationError
from ..rendering import render_pdf
from .base import BaseExporter


class PDFExporter(BaseExporter):
    """Export reports to PDF using ReportLab."""

    def export(self, report: Any, data: Any = None, context: Any = None) -> bytes:
        try:
            return render_pdf(
                _template_with_overrides(report, self.page_size, self.orientation),
                data or {},
            )
        except ReportValidationError as exc:
            raise ExporterError(str(exc)) from exc


def _template_with_overrides(report: Any, page_size: str | None, orientation: str | None) -> Any:
    if page_size is None and orientation is None:
        return report

    template = report.to_dict() if hasattr(report, "to_dict") else dict(report)
    page = dict(template.get("page", {}))
    if page_size is not None:
        page["size"] = page_size
        page["unit"] = page.get("unit", "px")
        page.pop("width", None)
        page.pop("height", None)
    if orientation is not None:
        page["orientation"] = orientation

    template["page"] = page
    return template
