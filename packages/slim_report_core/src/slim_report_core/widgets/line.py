"""Line widget implementation."""

from __future__ import annotations

from typing import Any, ClassVar

from ..models import ReportObject
from .base import BaseWidget, html_attr, object_style, pdf_y, set_pdf_stroke_color


class LineWidget(BaseWidget):
    """Render a straight line."""

    type: ClassVar[str] = "line"
    label: ClassVar[str] = "Line"

    def default_config(self) -> dict[str, Any]:
        return {
            "color": "#000000",
            "line_width": 1,
        }

    def render_html(self, obj: ReportObject, data: Any, context: Any) -> str:
        self.validate(obj)
        config = self.default_config() | obj.properties
        style = object_style(obj, extra={"overflow": "visible"})
        color = html_attr(config.get("color", "#000000"))
        line_width = float(config.get("line_width", 1))
        return (
            f'<svg data-slim-object="{html_attr(obj.id)}" style="{style}" '
            f'width="{obj.width}" height="{obj.height}" viewBox="0 0 {obj.width} {obj.height}" '
            'xmlns="http://www.w3.org/2000/svg">'
            f'<line x1="0" y1="0" x2="{obj.width}" y2="{obj.height}" '
            f'stroke="{color}" stroke-width="{line_width}" />'
            "</svg>"
        )

    def render_pdf(self, canvas: Any, obj: ReportObject, data: Any, context: Any) -> None:
        self.validate(obj)
        config = self.default_config() | obj.properties
        canvas.setLineWidth(float(config.get("line_width", 1)))
        set_pdf_stroke_color(canvas, config.get("color", "#000000"))
        canvas.line(obj.x, pdf_y(obj, context) + obj.height, obj.x + obj.width, pdf_y(obj, context))
