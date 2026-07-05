"""HTML renderer for report templates."""

from __future__ import annotations

from html import escape
from typing import Any

from ..exceptions import ReportValidationError
from ..report import Report
from .context import (
    RenderContext,
    RenderObject,
    create_render_context,
    object_px,
    resolve_object_value,
)


def render_html(report: Report, data: dict[str, Any] | None = None) -> str:
    """Render a report domain model and data as a full HTML document."""
    context = create_render_context(report, data)
    bands = "\n      ".join(render_html_band(band) for band in context.bands)
    objects = "\n      ".join(render_html_object(obj, context) for obj in context.objects)
    page = context.page
    title = escape(context.title)
    page_background = "#fff" if page.transparent else escape(page.background_color, quote=True)

    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        f"  <title>{title}</title>\n"
        "  <style>\n"
        "    body { margin: 0; background: #e5e7eb; font-family: Arial, sans-serif; }\n"
        "    .slim-report-preview { padding: 24px; }\n"
        "    .slim-report-page { position: relative; margin: 0 auto; background: #fff; "
        "box-shadow: 0 2px 12px rgba(15, 23, 42, 0.18); overflow: hidden; }\n"
        "    .slim-report-object { position: absolute; box-sizing: border-box; }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        '  <div class="slim-report-preview">\n'
        f'    <div class="slim-report-page" style="width: {page.width_px}px; '
        f'height: {page.height_px}px; background: {page_background};">\n'
        f"      {bands}\n"
        f"      {objects}\n"
        "    </div>\n"
        "  </div>\n"
        "</body>\n"
        "</html>\n"
    )


def render_html_band(band: Any) -> str:
    """Render a normalized band background as HTML."""
    if not band.visible:
        return ""
    background = escape(str(band.background_color), quote=True)
    if str(band.background_color).strip().lower() in {"", "none", "transparent"}:
        background = "transparent"
    return (
        f'<div class="slim-report-band" data-slim-band="{escape(band.id, quote=True)}" '
        f'style="position: absolute; left: 0; top: {band.y}px; width: 100%; '
        f'height: {band.height}px; box-sizing: border-box; background: {background};"></div>'
    )


def render_html_object(obj: RenderObject, context: RenderContext) -> str:
    """Render one normalized report object as HTML."""
    if not obj.visible:
        return ""
    if obj.type == "text":
        return _render_text(obj, context)
    if obj.type == "field":
        return _render_field(obj, context)
    if obj.type == "line":
        return _render_line(obj, context)
    if obj.type == "rectangle":
        return _render_rectangle(obj, context)
    if obj.type == "image":
        return _render_image(obj, context)
    raise ReportValidationError(f"Unsupported report object type: {obj.type}.")


def _render_text(obj: RenderObject, context: RenderContext) -> str:
    return _html_box(obj, context, escape(resolve_object_value(obj, context.data)))


def _render_field(obj: RenderObject, context: RenderContext) -> str:
    return _html_box(obj, context, escape(resolve_object_value(obj, context.data)))


def _render_line(obj: RenderObject, context: RenderContext) -> str:
    x, y, width, height = object_px(obj, context.page.unit)
    style = obj.style
    stroke_width = float(style.get("stroke_width", style.get("line_width", 1)))
    color = escape(
        str(style.get("stroke_color", style.get("color", style.get("border_color", "#000000")))),
        quote=True,
    )
    rendered_height = max(height, stroke_width)
    y1 = rendered_height / 2 if height == 0 else 0
    y2 = rendered_height / 2 if height == 0 else height
    return (
        f'<svg class="slim-report-object" data-slim-object="{escape(obj.id, quote=True)}" '
        f'style="{_position_style(x, y, width, rendered_height)}" '
        f'width="{width}" height="{rendered_height}" '
        f'viewBox="0 0 {width} {rendered_height}" xmlns="http://www.w3.org/2000/svg">'
        f'<line x1="0" y1="{y1}" x2="{width}" y2="{y2}" '
        f'stroke="{color}" stroke-width="{stroke_width}" />'
        "</svg>"
    )


def _render_rectangle(obj: RenderObject, context: RenderContext) -> str:
    x, y, width, height = object_px(obj, context.page.unit)
    style = obj.style
    border_width = float(style.get("border_width", style.get("stroke_width", 1)))
    border_color = escape(str(style.get("border_color", "#000000")), quote=True)
    border_radius = float(style.get("border_radius", 0))
    fill_color = escape(
        str(style.get("background_color", style.get("fill_color", "transparent"))),
        quote=True,
    )
    return (
        f'<div class="slim-report-object" data-slim-object="{escape(obj.id, quote=True)}" '
        f'style="{_position_style(x, y, width, height)} border: {border_width}px solid '
        f"{border_color}; border-radius: {border_radius}px; background: {fill_color};\"></div>"
    )


def _render_image(obj: RenderObject, context: RenderContext) -> str:
    x, y, width, height = object_px(obj, context.page.unit)
    style = obj.style
    source = str(obj.properties.get("src") or obj.properties.get("source") or "")
    border_width = float(style.get("border_width", 0))
    border_color = escape(str(style.get("border_color", "#000000")), quote=True)
    background_color = escape(str(style.get("background_color", "transparent")), quote=True)
    border_radius = float(style.get("border_radius", 0))
    opacity = float(style.get("opacity", 1))
    object_fit = escape(str(style.get("object_fit", "contain")), quote=True)
    css = (
        f"{_position_style(x, y, width, height)} "
        f"border: {border_width}px solid {border_color}; "
        f"border-radius: {border_radius}px; "
        f"background: {background_color}; opacity: {opacity}; "
        "display: grid; place-items: center; overflow: hidden;"
    )
    if not source:
        return (
            f'<div class="slim-report-object" data-slim-object="{escape(obj.id, quote=True)}" '
            f'style="{css}; color: #64748b;">Image</div>'
        )
    alt = escape(str(obj.properties.get("alt", "")), quote=True)
    return (
        f'<div class="slim-report-object" data-slim-object="{escape(obj.id, quote=True)}" '
        f'style="{css}"><img src="{escape(source, quote=True)}" alt="{alt}" '
        f'style="width: 100%; height: 100%; object-fit: {object_fit}; display: block;"></div>'
    )


def _html_box(obj: RenderObject, context: RenderContext, value: str) -> str:
    x, y, width, height = object_px(obj, context.page.unit)
    style = obj.style
    font_size = float(style.get("font_size", 12))
    font_family = escape(str(style.get("font_family", "Arial")), quote=True)
    line_height = style.get("line_height", 1.2)
    color = escape(str(style.get("color", "#000000")), quote=True)
    background_color = escape(str(style.get("background_color", "transparent")), quote=True)
    align = escape(str(style.get("align", "left")), quote=True)
    vertical_align = str(style.get("vertical_align", "top"))
    weight = "700" if bool(style.get("bold", False)) else "400"
    font_style = "italic" if bool(style.get("italic", False)) else "normal"
    decoration = "underline" if bool(style.get("underline", False)) else "none"
    css = (
        f"{_position_style(x, y, width, height)} "
        "display: flex; "
        f"justify-content: {_horizontal_flex_align(align)}; "
        f"align-items: {_vertical_flex_align(vertical_align)}; "
        f"font-family: {font_family}; font-size: {font_size}px; "
        f"line-height: {line_height}; "
        f"font-weight: {weight}; font-style: {font_style}; "
        f"text-decoration: {decoration}; color: {color}; "
        f"background: {background_color}; text-align: {align}; "
        "overflow: hidden; white-space: pre-wrap;"
    )
    return (
        f'<div class="slim-report-object" data-slim-object="{escape(obj.id, quote=True)}" '
        f'style="{css}">{value}</div>'
    )


def _position_style(x: float, y: float, width: float, height: float) -> str:
    return f"left: {x}px; top: {y}px; width: {width}px; height: {height}px;"


def _horizontal_flex_align(value: str) -> str:
    if value == "center":
        return "center"
    if value == "right":
        return "flex-end"
    return "flex-start"


def _vertical_flex_align(value: str) -> str:
    if value == "middle":
        return "center"
    if value == "bottom":
        return "flex-end"
    return "flex-start"
