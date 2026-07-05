"""Rectangle widget implementation."""

from __future__ import annotations

from typing import Any, ClassVar

from ..models import ReportObject
from .base import (
    BaseWidget,
    html_attr,
    object_style,
    pdf_y,
    set_pdf_fill_color,
    set_pdf_stroke_color,
)


class RectangleWidget(BaseWidget):
    """Render a rectangle."""

    type: ClassVar[str] = "rectangle"
    label: ClassVar[str] = "Rectangle"

    def default_config(self) -> dict[str, Any]:
        return {
            "border_color": "#000000",
            "border_width": 1,
            "fill_color": "transparent",
        }

    def render_html(self, obj: ReportObject, data: Any, context: Any) -> str:
        self.validate(obj)
        config = self.default_config() | obj.properties
        style = object_style(
            obj,
            extra={
                "border": (
                    f"{float(config.get('border_width', 1))}pt solid "
                    f"{html_attr(config.get('border_color', '#000000'))}"
                ),
                "background": html_attr(config.get("fill_color", "transparent")),
            },
        )
        return f'<div data-slim-object="{html_attr(obj.id)}" style="{style}"></div>'

    def render_pdf(self, canvas: Any, obj: ReportObject, data: Any, context: Any) -> None:
        self.validate(obj)
        config = self.default_config() | obj.properties
        canvas.setLineWidth(float(config.get("border_width", 1)))
        set_pdf_stroke_color(canvas, config.get("border_color", "#000000"))
        fill = set_pdf_fill_color(canvas, config.get("fill_color", "transparent"))
        canvas.rect(obj.x, pdf_y(obj, context), obj.width, obj.height, stroke=1, fill=int(fill))
