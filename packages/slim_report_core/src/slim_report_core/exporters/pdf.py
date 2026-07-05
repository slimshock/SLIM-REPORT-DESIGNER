"""PDF report exporter backed by ReportLab."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from ..exceptions import ExporterError
from .base import BaseExporter, object_to_points, render_context


class PDFExporter(BaseExporter):
    """Export reports to PDF using ReportLab."""

    def export(self, report: Any, data: Any = None, context: Any = None) -> bytes:
        canvas_class = _load_reportlab_canvas()

        template = self.normalize_template(report)
        layout = self.resolve_page_layout(template)
        renderer_context = render_context(context, layout)

        buffer = BytesIO()
        canvas = canvas_class(buffer, pagesize=(layout.width, layout.height))

        for obj in sorted(template.objects, key=lambda item: item.z_index):
            point_obj = object_to_points(obj, template.page.unit)
            widget = self.get_widget(point_obj)
            widget.render_pdf(canvas, point_obj, data or {}, renderer_context)

        canvas.showPage()
        canvas.save()
        return buffer.getvalue()


def _load_reportlab_canvas():
    try:
        from reportlab.pdfgen.canvas import Canvas
    except ImportError as exc:
        raise ExporterError(
            "PDF export requires ReportLab. Install slim-report-core[pdf] to use PDFExporter."
        ) from exc
    return Canvas

