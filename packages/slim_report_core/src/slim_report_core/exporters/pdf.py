"""PDF report exporter backed by ReportLab."""

from __future__ import annotations

from typing import Any

from ..exceptions import ExporterError, ReportValidationError
from ..rendering import render_pdf
from ..report import Report
from .base import BaseExporter, _page_size_values


class PDFExporter(BaseExporter):
    """Export reports to PDF using ReportLab."""

    def export(self, report: Any, data: Any = None, context: Any = None) -> bytes:
        try:
            if isinstance(report, Report):
                report.emit("before_export", exporter="pdf", data=data, context=context)
            asset_provider = _context_value(context, "asset_provider")
            asset_resolver = _context_value(context, "asset_resolver")
            result = render_pdf(
                _report_with_overrides(report, self.page_size, self.orientation),
                data or {},
                asset_provider=asset_provider,
                asset_resolver=asset_resolver,
            )
            if isinstance(report, Report):
                report.emit(
                    "after_export",
                    exporter="pdf",
                    data=data,
                    context=context,
                    result=result,
                )
            return result
        except ReportValidationError as exc:
            raise ExporterError(str(exc)) from exc


def _report_with_overrides(report: Any, page_size: str | None, orientation: str | None) -> Report:
    if isinstance(report, Report):
        prepared = report.clone(new_ids=False)
    else:
        raise ExporterError("Exporter expects a Report domain model.")

    if page_size is None and orientation is None:
        return prepared

    page = prepared.page
    if page_size is not None:
        width, height, unit = _page_size_values(page_size)
        page.size = page_size
        page.unit = unit
        page.width = width
        page.height = height
    if orientation is not None:
        page.orientation = orientation
    return prepared


def _context_value(context: Any, key: str) -> Any:
    if isinstance(context, dict):
        return context.get(key)
    return getattr(context, key, None)
