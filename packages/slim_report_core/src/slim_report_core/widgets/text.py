"""Text widget implementation."""

from __future__ import annotations

from typing import Any, ClassVar

from ..expressions import resolve_text
from ..models import ReportObject
from .base import (
    BaseWidget,
    html_attr,
    html_text,
    object_style,
    pdf_y,
    set_pdf_fill_color,
)


class TextWidget(BaseWidget):
    """Render static or expression-aware text."""

    type: ClassVar[str] = "text"
    label: ClassVar[str] = "Text"

    def default_config(self) -> dict[str, Any]:
        return {
            "text": "",
            "font_size": 10,
            "font_family": "Helvetica",
            "color": "#000000",
            "align": "left",
        }

    def render_html(self, obj: ReportObject, data: Any, context: Any) -> str:
        self.validate(obj)
        config = self.default_config() | obj.properties
        value = resolve_text(str(config.get("text", "")), data, context=context)
        style = object_style(
            obj,
            extra={
                "font-family": html_attr(config.get("font_family", "Helvetica")),
                "font-size": f"{float(config.get('font_size', 10))}pt",
                "color": html_attr(config.get("color", "#000000")),
                "text-align": html_attr(config.get("align", "left")),
                "overflow": "hidden",
                "white-space": "pre-wrap",
            },
        )
        return (
            f'<div data-slim-object="{html_attr(obj.id)}" style="{style}">'
            f"{html_text(value)}</div>"
        )

    def render_pdf(self, canvas: Any, obj: ReportObject, data: Any, context: Any) -> None:
        self.validate(obj)
        config = self.default_config() | obj.properties
        value = resolve_text(str(config.get("text", "")), data, context=context)

        canvas.setFont(
            str(config.get("font_family", "Helvetica")),
            float(config.get("font_size", 10)),
        )
        set_pdf_fill_color(canvas, config.get("color", "#000000"))
        baseline = pdf_y(obj, context) + max(obj.height - float(config.get("font_size", 10)), 0)
        canvas.drawString(obj.x, baseline, str(value))
