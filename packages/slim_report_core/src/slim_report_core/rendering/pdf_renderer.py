"""ReportLab PDF renderer for report templates."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from ..exceptions import ExporterError, ReportValidationError
from ..expressions import resolve_expression, resolve_text
from .context import RenderContext, RenderObject, create_render_context, object_pt


def render_pdf(template: Any, data: dict[str, Any] | None = None) -> bytes:
    """Render a report template and data as PDF bytes."""
    canvas_class = _load_canvas()
    context = create_render_context(template, data)
    buffer = BytesIO()
    canvas = canvas_class(buffer, pagesize=(context.page.width_pt, context.page.height_pt))

    for obj in context.objects:
        render_pdf_object(canvas, obj, context)

    canvas.showPage()
    canvas.save()
    return buffer.getvalue()


def render_pdf_object(canvas: Any, obj: RenderObject, context: RenderContext) -> None:
    """Render one normalized report object onto a ReportLab canvas."""
    if not obj.visible:
        return
    if obj.type == "text":
        _render_text(canvas, obj, context)
        return
    if obj.type == "field":
        _render_field(canvas, obj, context)
        return
    if obj.type == "line":
        _render_line(canvas, obj, context)
        return
    if obj.type == "rectangle":
        _render_rectangle(canvas, obj, context)
        return
    raise ReportValidationError(f"Unsupported report object type: {obj.type}.")


def _render_text(canvas: Any, obj: RenderObject, context: RenderContext) -> None:
    value = resolve_text(obj.text, context.data)
    _draw_text(canvas, obj, context, str(value))


def _render_field(canvas: Any, obj: RenderObject, context: RenderContext) -> None:
    value = resolve_expression(obj.binding, context.data)
    _draw_text(canvas, obj, context, str(value))


def _render_line(canvas: Any, obj: RenderObject, context: RenderContext) -> None:
    x, y, width, height = object_pt(obj, context.page.unit)
    style = obj.style
    stroke_width = float(style.get("stroke_width", style.get("line_width", 1)))
    canvas.setLineWidth(stroke_width)
    _set_stroke_color(canvas, style.get("color", style.get("border_color", "#000000")))
    canvas.line(x, _pdf_y(context, y), x + width, _pdf_y(context, y + height))


def _render_rectangle(canvas: Any, obj: RenderObject, context: RenderContext) -> None:
    x, y, width, height = object_pt(obj, context.page.unit)
    style = obj.style
    canvas.setLineWidth(float(style.get("border_width", style.get("stroke_width", 1))))
    _set_stroke_color(canvas, style.get("border_color", "#000000"))
    fill = _set_fill_color(canvas, style.get("fill_color", "transparent"))
    canvas.rect(x, _pdf_y(context, y + height), width, height, stroke=1, fill=int(fill))


def _draw_text(canvas: Any, obj: RenderObject, context: RenderContext, value: str) -> None:
    x, y, _width, _height = object_pt(obj, context.page.unit)
    style = obj.style
    font_size = float(style.get("font_size", 12))
    font_family = str(style.get("font_family", "Helvetica"))
    if bool(style.get("bold", False)) and font_family == "Helvetica":
        font_family = "Helvetica-Bold"

    canvas.setFont(font_family, font_size)
    _set_fill_color(canvas, style.get("color", "#000000"))
    canvas.drawString(x, _pdf_y(context, y) - font_size, value)


def _pdf_y(context: RenderContext, top_y: float) -> float:
    return context.page.height_pt - top_y


def _set_fill_color(canvas: Any, color: Any) -> bool:
    if _is_transparent(color):
        return False
    canvas.setFillColor(_hex_color(color))
    return True


def _set_stroke_color(canvas: Any, color: Any) -> bool:
    if _is_transparent(color):
        return False
    canvas.setStrokeColor(_hex_color(color))
    return True


def _hex_color(color: Any) -> Any:
    from reportlab.lib.colors import HexColor

    return HexColor(str(color))


def _is_transparent(color: Any) -> bool:
    if color is None:
        return True
    return str(color).strip().lower() in {"", "none", "transparent"}


def _load_canvas() -> Any:
    try:
        from reportlab.pdfgen.canvas import Canvas
    except ImportError as exc:
        raise ExporterError(
            "PDF export requires ReportLab. Install reportlab or slim-report-core[pdf]."
        ) from exc
    return Canvas
