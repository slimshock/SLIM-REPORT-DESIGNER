"""Base classes and helpers for report widgets."""

from __future__ import annotations

from abc import ABC, abstractmethod
from html import escape
from typing import Any, ClassVar

from ..exceptions import WidgetValidationError
from ..models import ReportObject


class BaseWidget(ABC):
    """Base class for all report object widgets."""

    type: ClassVar[str]
    label: ClassVar[str]

    def default_config(self) -> dict[str, Any]:
        """Return default widget properties."""
        return {}

    def validate(self, obj: ReportObject) -> None:
        """Validate a report object before rendering."""
        if obj.type != self.type:
            raise WidgetValidationError(
                f"Widget {self.type!r} cannot render object type {obj.type!r}."
            )
        if not obj.id.strip():
            raise WidgetValidationError("Report object id must be a non-empty string.")
        if obj.width < 0 or obj.height < 0:
            raise WidgetValidationError("Report object width and height cannot be negative.")

    @abstractmethod
    def render_html(self, obj: ReportObject, data: Any, context: Any) -> str:
        """Render this widget as absolute-positioned HTML."""

    @abstractmethod
    def render_pdf(self, canvas: Any, obj: ReportObject, data: Any, context: Any) -> None:
        """Render this widget on a ReportLab canvas."""


def object_style(obj: ReportObject, *, extra: dict[str, str] | None = None) -> str:
    """Build the common absolute-positioned CSS for a report object."""
    styles = {
        "position": "absolute",
        "left": f"{obj.x}pt",
        "top": f"{obj.y}pt",
        "width": f"{obj.width}pt",
        "height": f"{obj.height}pt",
        "z-index": str(obj.z_index),
        "box-sizing": "border-box",
    }
    if not obj.visible:
        styles["display"] = "none"
    if extra:
        styles.update(extra)
    return "; ".join(f"{key}: {value}" for key, value in styles.items())


def pdf_y(obj: ReportObject, context: Any) -> float:
    """Convert a top-origin object y coordinate into ReportLab's bottom-origin space."""
    page_height = 0.0
    if isinstance(context, dict):
        page_height = float(context.get("_slim_report_page_height_pt", 0.0))
    return page_height - obj.y - obj.height


def set_pdf_fill_color(canvas: Any, color: Any) -> bool:
    """Set a ReportLab fill color when a visible color is provided."""
    if _is_transparent(color):
        return False

    from reportlab.lib.colors import HexColor

    canvas.setFillColor(HexColor(str(color)))
    return True


def set_pdf_stroke_color(canvas: Any, color: Any) -> bool:
    """Set a ReportLab stroke color when a visible color is provided."""
    if _is_transparent(color):
        return False

    from reportlab.lib.colors import HexColor

    canvas.setStrokeColor(HexColor(str(color)))
    return True


def html_attr(value: Any) -> str:
    """Escape a value for safe HTML attributes."""
    return escape(str(value), quote=True)


def html_text(value: Any) -> str:
    """Escape a value for safe HTML text content."""
    return escape(str(value))


def _is_transparent(color: Any) -> bool:
    if color is None:
        return True
    return str(color).strip().lower() in {"", "none", "transparent"}
