"""ReportLab PDF renderer for report templates."""

from __future__ import annotations

import base64
from io import BytesIO
from typing import Any

from ..exceptions import ExporterError, ReportValidationError
from ..report import Report
from .context import (
    RenderContext,
    RenderObject,
    convert_unit,
    create_render_context,
    object_pt,
    resolve_object_value,
)


def render_pdf(report: Report, data: dict[str, Any] | None = None) -> bytes:
    """Render a report domain model and data as PDF bytes."""
    canvas_class = _load_canvas()
    context = create_render_context(report, data)
    buffer = BytesIO()
    canvas = canvas_class(buffer, pagesize=(context.page.width_pt, context.page.height_pt))
    if not context.page.transparent:
        _set_fill_color(canvas, context.page.background_color)
        canvas.rect(0, 0, context.page.width_pt, context.page.height_pt, stroke=0, fill=1)

    for band in context.bands:
        _render_band(canvas, band, context)

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
    if obj.type == "image":
        _render_image(canvas, obj, context)
        return
    raise ReportValidationError(f"Unsupported report object type: {obj.type}.")


def _render_band(canvas: Any, band: Any, context: RenderContext) -> None:
    if not getattr(band, "visible", True):
        return
    background = getattr(band, "background_color", "transparent")
    if _is_transparent(background):
        return
    y = convert_unit(float(getattr(band, "y", 0) or 0), "px", "pt")
    height = convert_unit(float(getattr(band, "height", 0) or 0), "px", "pt")
    _set_fill_color(canvas, background)
    canvas.rect(0, _pdf_y(context, y + height), context.page.width_pt, height, stroke=0, fill=1)


def _render_text(canvas: Any, obj: RenderObject, context: RenderContext) -> None:
    _draw_text(canvas, obj, context, resolve_object_value(obj, context.data))


def _render_field(canvas: Any, obj: RenderObject, context: RenderContext) -> None:
    _draw_text(canvas, obj, context, resolve_object_value(obj, context.data))


def _render_line(canvas: Any, obj: RenderObject, context: RenderContext) -> None:
    x, y, width, height = object_pt(obj, context.page.unit)
    style = obj.style
    stroke_width = _style_length_pt(style.get("stroke_width", style.get("line_width", 1)), context)
    canvas.setLineWidth(stroke_width)
    _set_stroke_color(
        canvas,
        style.get("stroke_color", style.get("color", style.get("border_color", "#000000"))),
    )
    canvas.line(x, _pdf_y(context, y), x + width, _pdf_y(context, y + height))


def _render_rectangle(canvas: Any, obj: RenderObject, context: RenderContext) -> None:
    x, y, width, height = object_pt(obj, context.page.unit)
    style = obj.style
    border_width = _style_length_pt(style.get("border_width", style.get("stroke_width", 1)), context)
    border_radius = _style_length_pt(style.get("border_radius", 0), context)
    canvas.setLineWidth(border_width)
    _set_stroke_color(canvas, style.get("border_color", "#000000"))
    fill = _set_fill_color(
        canvas,
        style.get("background_color", style.get("fill_color", "transparent")),
    )
    if border_radius > 0:
        canvas.roundRect(
            x,
            _pdf_y(context, y + height),
            width,
            height,
            radius=border_radius,
            stroke=1,
            fill=int(fill),
        )
    else:
        canvas.rect(x, _pdf_y(context, y + height), width, height, stroke=1, fill=int(fill))


def _render_image(canvas: Any, obj: RenderObject, context: RenderContext) -> None:
    x, y, width, height = object_pt(obj, context.page.unit)
    style = obj.style
    background = style.get("background_color", "transparent")
    if not _is_transparent(background):
        _set_fill_color(canvas, background)
        canvas.rect(x, _pdf_y(context, y + height), width, height, stroke=0, fill=1)

    border_width = _style_length_pt(style.get("border_width", 0), context)
    if border_width > 0:
        canvas.setLineWidth(border_width)
        _set_stroke_color(canvas, style.get("border_color", "#000000"))
        canvas.rect(x, _pdf_y(context, y + height), width, height, stroke=1, fill=0)

    source = str(obj.properties.get("src") or obj.properties.get("source") or "")
    reader = _image_reader(source)
    if reader is None:
        _draw_image_placeholder(canvas, x, y, width, height, context)
        return
    try:
        _set_alpha(canvas, float(style.get("opacity", 1)))
        canvas.drawImage(
            reader,
            x,
            _pdf_y(context, y + height),
            width=width,
            height=height,
            preserveAspectRatio=str(style.get("object_fit", "contain")) == "contain",
            mask="auto",
        )
        _set_alpha(canvas, 1)
    except Exception:
        _set_alpha(canvas, 1)
        _draw_image_placeholder(canvas, x, y, width, height, context)


def _draw_image_placeholder(
    canvas: Any,
    x: float,
    y: float,
    width: float,
    height: float,
    context: RenderContext,
) -> None:
    canvas.setLineWidth(1)
    _set_stroke_color(canvas, "#94a3b8")
    canvas.rect(x, _pdf_y(context, y + height), width, height, stroke=1, fill=0)
    canvas.setFont("Helvetica", 9)
    _set_fill_color(canvas, "#64748b")
    canvas.drawString(x + 4, _pdf_y(context, y + (height / 2)), "Image")


def _image_reader(source: str) -> Any | None:
    if not source:
        return None
    if source.startswith(("http://", "https://")):
        return None
    try:
        from reportlab.lib.utils import ImageReader
    except ImportError:
        return None
    if source.startswith("data:image/"):
        try:
            _, encoded = source.split(",", 1)
            return ImageReader(BytesIO(base64.b64decode(encoded)))
        except Exception:
            return None
    try:
        return ImageReader(source)
    except Exception:
        return None


def _draw_text(canvas: Any, obj: RenderObject, context: RenderContext, value: str) -> None:
    x, y, width, height = object_pt(obj, context.page.unit)
    style = obj.style
    font_size = _font_size_pt(style.get("font_size", 12), context)
    font_family = _font_name(
        str(style.get("font_family", "Helvetica")),
        bold=bool(style.get("bold", False)),
        italic=bool(style.get("italic", False)),
    )

    background = style.get("background_color", "transparent")
    if not _is_transparent(background):
        _set_fill_color(canvas, background)
        canvas.rect(x, _pdf_y(context, y + height), width, height, stroke=0, fill=1)

    canvas.setFont(font_family, font_size)
    _set_fill_color(canvas, style.get("color", "#000000"))
    text_width = canvas.stringWidth(value, font_family, font_size)
    align = str(style.get("align", "left"))
    text_x = x
    if align == "center":
        text_x = x + max((width - text_width) / 2, 0)
    elif align == "right":
        text_x = x + max(width - text_width, 0)
    baseline = _pdf_y(context, y) - font_size
    vertical_align = str(style.get("vertical_align", "top"))
    if vertical_align == "middle":
        baseline = _pdf_y(context, y + (height / 2) - (font_size / 2))
    elif vertical_align == "bottom":
        baseline = _pdf_y(context, y + height)
    canvas.drawString(text_x, baseline, value)
    if bool(style.get("underline", False)):
        canvas.setLineWidth(max(font_size / 16, 0.5))
        _set_stroke_color(canvas, style.get("color", "#000000"))
        canvas.line(text_x, baseline - 1, text_x + text_width, baseline - 1)


def _font_name(font_family: str, *, bold: bool, italic: bool) -> str:
    base = font_family if font_family in {"Helvetica", "Times-Roman", "Courier"} else "Helvetica"
    if base == "Times-Roman":
        if bold and italic:
            return "Times-BoldItalic"
        if bold:
            return "Times-Bold"
        if italic:
            return "Times-Italic"
        return base
    if base == "Courier":
        if bold and italic:
            return "Courier-BoldOblique"
        if bold:
            return "Courier-Bold"
        if italic:
            return "Courier-Oblique"
        return base
    if bold and italic:
        return "Helvetica-BoldOblique"
    if bold:
        return "Helvetica-Bold"
    if italic:
        return "Helvetica-Oblique"
    return base


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

    try:
        return HexColor(str(color))
    except Exception:
        return HexColor("#000000")


def _is_transparent(color: Any) -> bool:
    if color is None:
        return True
    return str(color).strip().lower() in {"", "none", "transparent"}


def _font_size_pt(value: Any, context: RenderContext) -> float:
    size = float(value or 12)
    if context.page.unit == "px":
        return convert_unit(size, "px", "pt")
    return size


def _style_length_pt(value: Any, context: RenderContext) -> float:
    length = float(value or 0)
    if context.page.unit == "px":
        return convert_unit(length, "px", "pt")
    return length


def _set_alpha(canvas: Any, value: float) -> None:
    alpha = max(0.0, min(value, 1.0))
    setter = getattr(canvas, "setFillAlpha", None)
    if callable(setter):
        setter(alpha)


def _load_canvas() -> Any:
    try:
        from reportlab.pdfgen.canvas import Canvas
    except ImportError as exc:
        raise ExporterError(
            "PDF export requires ReportLab. Install reportlab or reinstall slim-report-core."
        ) from exc
    return Canvas
