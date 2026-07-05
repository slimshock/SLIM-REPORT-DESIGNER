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
    objects = "\n      ".join(render_html_object(obj, context) for obj in context.objects)
    page = context.page
    title = escape(context.title)

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
        f'height: {page.height_px}px;">\n'
        f"      {objects}\n"
        "    </div>\n"
        "  </div>\n"
        "</body>\n"
        "</html>\n"
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
    raise ReportValidationError(f"Unsupported report object type: {obj.type}.")


def _render_text(obj: RenderObject, context: RenderContext) -> str:
    return _html_box(obj, context, escape(resolve_object_value(obj, context.data)))


def _render_field(obj: RenderObject, context: RenderContext) -> str:
    return _html_box(obj, context, escape(resolve_object_value(obj, context.data)))


def _render_line(obj: RenderObject, context: RenderContext) -> str:
    x, y, width, height = object_px(obj, context.page.unit)
    style = obj.style
    stroke_width = float(style.get("stroke_width", style.get("line_width", 1)))
    color = escape(str(style.get("color", style.get("border_color", "#000000"))), quote=True)
    return (
        f'<svg class="slim-report-object" data-slim-object="{escape(obj.id, quote=True)}" '
        f'style="{_position_style(x, y, width, height)}" '
        f'width="{width}" height="{max(height, stroke_width)}" '
        f'viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">'
        f'<line x1="0" y1="0" x2="{width}" y2="{height}" '
        f'stroke="{color}" stroke-width="{stroke_width}" />'
        "</svg>"
    )


def _render_rectangle(obj: RenderObject, context: RenderContext) -> str:
    x, y, width, height = object_px(obj, context.page.unit)
    style = obj.style
    border_width = float(style.get("border_width", style.get("stroke_width", 1)))
    border_color = escape(str(style.get("border_color", "#000000")), quote=True)
    fill_color = escape(str(style.get("fill_color", "transparent")), quote=True)
    return (
        f'<div class="slim-report-object" data-slim-object="{escape(obj.id, quote=True)}" '
        f'style="{_position_style(x, y, width, height)} border: {border_width}px solid '
        f"{border_color}; background: {fill_color};\"></div>"
    )


def _html_box(obj: RenderObject, context: RenderContext, value: str) -> str:
    x, y, width, height = object_px(obj, context.page.unit)
    style = obj.style
    font_size = float(style.get("font_size", 12))
    font_family = escape(str(style.get("font_family", "Arial")), quote=True)
    color = escape(str(style.get("color", "#000000")), quote=True)
    align = escape(str(style.get("align", "left")), quote=True)
    weight = "700" if bool(style.get("bold", False)) else "400"
    css = (
        f"{_position_style(x, y, width, height)} "
        f"font-family: {font_family}; font-size: {font_size}px; "
        f"font-weight: {weight}; color: {color}; text-align: {align}; "
        "overflow: hidden; white-space: pre-wrap;"
    )
    return (
        f'<div class="slim-report-object" data-slim-object="{escape(obj.id, quote=True)}" '
        f'style="{css}">{value}</div>'
    )


def _position_style(x: float, y: float, width: float, height: float) -> str:
    return f"left: {x}px; top: {y}px; width: {width}px; height: {height}px;"
