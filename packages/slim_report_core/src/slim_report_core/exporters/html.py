"""HTML report exporter."""

from __future__ import annotations

from typing import Any

from ..exceptions import ExporterError, ReportValidationError
from ..rendering import render_html
from ..report import Report
from .base import BaseExporter


class HTMLExporter(BaseExporter):
    """Export reports to absolute-positioned HTML."""

    def export(self, report: Any, data: Any = None, context: Any = None) -> str:
        try:
            if isinstance(report, Report):
                report.emit("before_export", exporter="html", data=data, context=context)
            result = render_html(
                _report_with_overrides(report, self.page_size, self.orientation),
                data or {},
            )
            if isinstance(report, Report):
                report.emit(
                    "after_export",
                    exporter="html",
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
        page.size = page_size
        page.unit = page.unit or "px"
    if orientation is not None:
        page.orientation = orientation
    return prepared
