"""HTML renderer for report templates."""

from __future__ import annotations

from html import escape
from typing import Any

from ..assets.resolver import resolve_image_source
from ..exceptions import ReportValidationError
from ..report import Report
from .context import (
    RenderContext,
    RenderObject,
    context_with_page_numbers,
    create_render_context,
    get_array_by_path,
    get_row_value,
    get_value_by_path,
    object_px,
    object_with_conditional_style,
    resolve_bound_object_value,
    resolve_grouped_object_value,
    resolve_object_value,
    resolve_repeated_object_value,
)
from .pagination import build_render_pages
from .qrcode import QR_GRID_SIZE, qr_module_matrix


def render_html(
    report: Report,
    data: dict[str, Any] | None = None,
    *,
    asset_provider: Any | None = None,
    asset_resolver: Any | None = None,
) -> str:
    """Render a report domain model and data as a full HTML document."""
    context = create_render_context(
        report,
        data,
        asset_provider=asset_provider,
        asset_resolver=asset_resolver,
    )
    page = context.page
    title = escape(context.title)
    page_background = "#fff" if page.transparent else escape(page.background_color, quote=True)
    print_settings = getattr(report.page, "print", {}) or {}
    show_print_button = bool(print_settings.get("show_browser_print_button", True))
    print_toolbar = (
        '  <div class="slim-report-preview-toolbar">'
        '<button class="slim-report-print-button" type="button" onclick="window.print()">'
        "Print</button>"
        "</div>\n"
        if show_print_button
        else ""
    )
    pages = build_render_pages(context)
    page_html = "\n".join(
        render_html_page(plan, context, page_background, len(pages)) for plan in pages
    )

    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        f"  <title>{title}</title>\n"
        "  <style>\n"
        f"    @page {{ size: {page.width_px}px {page.height_px}px; margin: 0; }}\n"
        "    html, body { width: 100%; min-height: 100%; }\n"
        "    body { margin: 0; background: #e5e7eb; font-family: Arial, sans-serif; }\n"
        "    .slim-report-preview-toolbar { position: sticky; top: 0; z-index: 10; "
        "padding: 12px 24px; background: rgba(255, 255, 255, 0.96); "
        "border-bottom: 1px solid #d1d5db; }\n"
        "    .slim-report-print-button { border: 1px solid #94a3b8; background: #fff; "
        "border-radius: 4px; padding: 6px 10px; font: 600 12px Arial, sans-serif; "
        "color: #111827; cursor: pointer; }\n"
        "    .slim-report-preview { padding: 24px; display: grid; gap: 24px; }\n"
        "    .slim-report-page { position: relative; margin: 0 auto; background: #fff; "
        "box-shadow: 0 2px 12px rgba(15, 23, 42, 0.18); overflow: hidden; "
        "break-after: page; page-break-after: always; -webkit-print-color-adjust: exact; "
        "print-color-adjust: exact; }\n"
        "    .slim-report-page:last-child { break-after: auto; page-break-after: auto; }\n"
        "    .slim-report-page-number { position: absolute; right: 12px; bottom: 8px; "
        "font: 10px Arial, sans-serif; color: #94a3b8; }\n"
        "    .slim-report-object { position: absolute; box-sizing: border-box; }\n"
        "    @media print { html, body { margin: 0; background: #fff; } "
        ".slim-report-preview-toolbar, .slim-report-print-button, button "
        "{ display: none !important; } "
        ".slim-report-preview { padding: 0; gap: 0; } "
        ".slim-report-page { margin: 0; box-shadow: none; break-after: page; "
        "page-break-after: always; } "
        ".slim-report-page:last-child { break-after: auto; page-break-after: auto; } "
        "* { -webkit-print-color-adjust: exact; print-color-adjust: exact; } }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        f"{print_toolbar}"
        '  <div class="slim-report-preview">\n'
        f"{page_html}"
        "  </div>\n"
        "</body>\n"
        "</html>\n"
    )


def render_html_page(
    plan: Any,
    context: RenderContext,
    page_background: str,
    total_pages: int,
) -> str:
    bands = "\n      ".join(render_html_band(band) for band in plan.bands)
    page = context.page
    page_number = plan.index + 1
    objects = "\n      ".join(
        render_html_object(
            obj,
            context_with_page_numbers(object_context, page_number, total_pages),
        )
        for obj, object_context in plan.objects
    )
    return (
        f'    <div class="slim-report-page" data-slim-page="{page_number}" '
        f'style="width: {page.width_px}px; height: {page.height_px}px; '
        f'background: {page_background};">\n'
        f"      {bands}\n"
        f"      {objects}\n"
        f'      <div class="slim-report-page-number">Page {page_number}</div>\n'
        "    </div>\n"
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
    resolved_obj = object_with_conditional_style(obj, context.data)
    if resolved_obj is None:
        return ""
    obj = resolved_obj
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
    if obj.type == "table":
        return _render_table(obj, context)
    if obj.type == "barcode":
        return _render_barcode(obj, context)
    if obj.type == "qrcode":
        return _render_qrcode(obj, context)
    raise ReportValidationError(f"Unsupported report object type: {obj.type}.")


def render_html_objects(context: RenderContext) -> list[str]:
    repeat = _detail_repeat(context)
    if not repeat:
        return [render_html_object(obj, context) for obj in context.objects]
    data_path = str(repeat.get("data_path", ""))
    rows = get_array_by_path(context.data, data_path)
    detail_objects = [obj for obj in context.objects if obj.band == "detail"]
    rendered = [render_html_object(obj, context) for obj in context.objects if obj.band != "detail"]
    if not rows:
        rendered.append(_empty_message_html(context, repeat))
        return rendered
    row_height = float(repeat.get("row_height", 22) or 22)
    for row_index, row in enumerate(rows):
        row_data = row if isinstance(row, dict) else {}
        for obj in detail_objects:
            repeated = RenderObject(
                **{
                    **obj.__dict__,
                    "id": f"{obj.id}__row_{row_index}",
                    "y": obj.y + (row_index * row_height),
                }
            )
            rendered.append(
                render_html_object(repeated, context_with_row(context, row_data, data_path))
            )
    return rendered


def context_with_row(context: RenderContext, row: dict[str, Any], data_path: str) -> RenderContext:
    return RenderContext(
        report=context.report,
        data={**dict(context.data), "__slim_row__": row, "__slim_repeat_path__": data_path},
        page=context.page,
        bands=context.bands,
        objects=context.objects,
        title=context.title,
        asset_provider=context.asset_provider,
        asset_resolver=context.asset_resolver,
    )


def _render_text(obj: RenderObject, context: RenderContext) -> str:
    if _group_context(context) is not None:
        return _html_box(obj, context, escape(resolve_grouped_object_value(obj, context.data)))
    return _html_box(obj, context, escape(resolve_object_value(obj, context.data)))


def _render_field(obj: RenderObject, context: RenderContext) -> str:
    row = context.data.get("__slim_row__") if isinstance(context.data, dict) else None
    repeat_path = (
        context.data.get("__slim_repeat_path__", "") if isinstance(context.data, dict) else ""
    )
    if isinstance(row, dict) and _group_context(context) is not None:
        value = resolve_grouped_object_value(obj, context.data, row, str(repeat_path))
    elif isinstance(row, dict):
        value = resolve_repeated_object_value(obj, context.data, row, str(repeat_path))
    elif _group_context(context) is not None:
        value = resolve_grouped_object_value(obj, context.data)
    else:
        value = resolve_object_value(obj, context.data)
    return _html_box(obj, context, escape(value))


def _group_context(context: RenderContext) -> Any | None:
    return context.data.get("__slim_group__") if isinstance(context.data, dict) else None


def _object_value(obj: RenderObject, context: RenderContext) -> str:
    row = context.data.get("__slim_row__") if isinstance(context.data, dict) else None
    repeat_path = (
        context.data.get("__slim_repeat_path__", "") if isinstance(context.data, dict) else ""
    )
    return resolve_bound_object_value(
        obj,
        context.data,
        row if isinstance(row, dict) else None,
        str(repeat_path),
    )


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
        f'{border_color}; border-radius: {border_radius}px; background: {fill_color};"></div>'
    )


def _render_image(obj: RenderObject, context: RenderContext) -> str:
    x, y, width, height = object_px(obj, context.page.unit)
    style = obj.style
    resolved_source = _resolved_image_source(obj, context)
    source = resolved_source.as_data_url()
    if not source:
        source = resolved_source.source
    source = _image_source(source)
    asset_id = _image_asset_id(obj)
    if asset_id and not source:
        source = ""
    elif not asset_id and not source:
        source = _image_source(
            obj.properties.get("src") or obj.properties.get("source") or _object_value(obj, context)
        )
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
            f'style="{css}"></div>'
        )
    alt = escape(str(obj.properties.get("alt", "")), quote=True)
    return (
        f'<div class="slim-report-object" data-slim-object="{escape(obj.id, quote=True)}" '
        f'style="{css}"><img src="{escape(source, quote=True)}" alt="{alt}" '
        f'style="width: 100%; height: 100%; object-fit: {object_fit}; display: block;"></div>'
    )


def _image_source(value: Any) -> str:
    text = str(value or "").strip()
    if text.lower() in {"", "none", "null", "undefined"}:
        return ""
    if text.startswith("{{") and text.endswith("}}"):
        return ""
    return text


def _resolved_image_source(obj: RenderObject, context: RenderContext) -> Any:
    resolver = context.asset_resolver
    source = (
        obj.properties.get("src")
        or obj.properties.get("source")
        or _object_value(obj, context)
    )
    asset_id = _image_asset_id(obj)
    if resolver is not None and hasattr(resolver, "resolve"):
        return resolver.resolve(
            source=source,
            asset_id=asset_id,
            prefer_url=True,
            prefer_bytes=False,
        )
    return resolve_image_source(
        source=source,
        asset_id=asset_id,
        asset_provider=context.asset_provider,
        prefer_url=True,
        prefer_bytes=False,
    )


def _image_asset_id(obj: RenderObject) -> str:
    return str(
        obj.properties.get("assetId")
        or obj.properties.get("asset_id")
        or obj.properties.get("asset")
        or ""
    ).strip()


def _render_barcode(obj: RenderObject, context: RenderContext) -> str:
    x, y, width, height = object_px(obj, context.page.unit)
    value = escape(_object_value(obj, context) or "Barcode")
    style = obj.style
    foreground = escape(str(style.get("foreground_color", "#111827")), quote=True)
    background = escape(str(style.get("background_color", "#ffffff")), quote=True)
    font_size = float(style.get("font_size", 8) or 8)
    show_text = bool(obj.properties.get("show_text", True))
    bars_height = max(height - (font_size + 6 if show_text else 0), 8)
    wrapper_style = (
        f"{_position_style(x, y, width, height)} "
        f"background: {background}; color: {foreground}; overflow: hidden; "
        "display: grid; grid-template-rows: minmax(0, 1fr) auto; padding: 2px;"
    )
    bars_style = (
        f"height: {bars_height}px; min-height: 8px; background: "
        f"repeating-linear-gradient(90deg, {foreground} 0 2px, transparent 2px 4px, "
        f"{foreground} 4px 5px, transparent 5px 9px);"
    )
    text_html = (
        f'<div style="font: {font_size}px Arial, sans-serif; text-align: center; '
        'white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">'
        f"{value}</div>"
        if show_text
        else ""
    )
    return (
        f'<div class="slim-report-object slim-report-barcode" '
        f'data-slim-object="{escape(obj.id, quote=True)}" style="{wrapper_style}">'
        f'<div aria-hidden="true" style="{bars_style}"></div>{text_html}</div>'
    )


def _render_qrcode(obj: RenderObject, context: RenderContext) -> str:
    x, y, width, height = object_px(obj, context.page.unit)
    value = escape(_object_value(obj, context) or "QR Code")
    style = obj.style
    foreground = escape(str(style.get("foreground_color", "#111827")), quote=True)
    background = escape(str(style.get("background_color", "#ffffff")), quote=True)
    size = min(width, height)
    qr_x = max((width - size) / 2, 0)
    qr_y = max((height - size) / 2, 0)
    wrapper_style = (
        f"{_position_style(x, y, width, height)} "
        f"background: {background}; color: {foreground}; overflow: hidden; "
        "position: absolute;"
    )
    qr_style = (
        f"position: absolute; left: {qr_x}px; top: {qr_y}px; "
        f"width: {size}px; height: {size}px; box-sizing: border-box; "
        "display: block;"
    )
    return (
        f'<div class="slim-report-object slim-report-qrcode" '
        f'data-slim-object="{escape(obj.id, quote=True)}" title="{value}" '
        f'style="{wrapper_style}">{_qr_svg(value, qr_style, foreground, background)}</div>'
    )


def _qr_svg(value: str, style: str, foreground: str, background: str) -> str:
    background_rect = (
        f'<rect width="{QR_GRID_SIZE}" height="{QR_GRID_SIZE}" fill="{background}" />'
        if not _is_transparent(background)
        else ""
    )
    modules = []
    for row_index, row in enumerate(qr_module_matrix(value)):
        for col_index, enabled in enumerate(row):
            if enabled:
                modules.append(f'<rect x="{col_index}" y="{row_index}" width="1" height="1" />')
    module_html = "".join(modules)
    return (
        f'<svg aria-label="{value}" role="img" style="{style}" '
        f'viewBox="0 0 {QR_GRID_SIZE} {QR_GRID_SIZE}" '
        'xmlns="http://www.w3.org/2000/svg" shape-rendering="crispEdges">'
        f"{background_rect}<g fill=\"{foreground}\">{module_html}</g></svg>"
    )


def _render_table(obj: RenderObject, context: RenderContext) -> str:
    x, y, width, height = object_px(obj, context.page.unit)
    spec = _table_spec(obj)
    columns = spec["columns"]
    rows_override = obj.properties.get("__slim_table_rows__")
    row_offset = int(obj.properties.get("__slim_table_row_offset__", 0) or 0)
    rows = (
        rows_override
        if isinstance(rows_override, list)
        else get_array_by_path(context.data, spec["data_path"])
    )
    row_height = float(spec["row"].get("height", 22) or 22)
    header_height = (
        float(spec["header"].get("height", 24) or 24) if spec["header"].get("visible", True) else 0
    )
    available_height = max(height - header_height, 0)
    max_rows = max(0, int(available_height // max(row_height, 1)))
    visible_rows = rows[:max_rows]
    border_width = float(spec["border"].get("width", 1) or 0)
    border_color = escape(str(spec["border"].get("color", "#d1d5db")), quote=True)
    radius = float(obj.style.get("border_radius", 0) or 0)
    background = escape(str(obj.style.get("background_color", "#ffffff")), quote=True)
    colgroup = "".join(
        f'<col style="width: {_column_width_percent(column, columns):.4f}%;">' for column in columns
    )
    header_html = ""
    if spec["header"].get("visible", True):
        header_background = escape(
            str(spec["header"].get("background_color", "#e5e7eb")),
            quote=True,
        )
        header_cells = "".join(
            _table_cell(
                column.get("label", column.get("binding", "")),
                align=str(column.get("align", "left")),
                tag="th",
                style=(
                    f"height: {header_height}px; "
                    f"background: {header_background}; "
                    f"color: {escape(str(spec['header'].get('color', '#111827')), quote=True)}; "
                    f"font-size: {float(spec['header'].get('font_size', 10) or 10)}px; "
                    f"font-weight: {'700' if spec['header'].get('bold', True) else '400'};"
                ),
            )
            for column in columns
        )
        header_html = f"<thead><tr>{header_cells}</tr></thead>"
    if visible_rows:
        body_rows = []
        for row_index, row in enumerate(visible_rows):
            row_data = row if isinstance(row, dict) else {}
            row_bg = (
                spec["row"].get("alternate_background_color")
                if (row_offset + row_index) % 2 == 1
                else spec["row"].get("background_color", "#ffffff")
            )
            cells = "".join(
                _table_cell(
                    _table_cell_value(column, row_data, spec["data_path"], context),
                    align=str(column.get("align", "left")),
                    style=(
                        f"height: {row_height}px; "
                        f"background: {escape(str(row_bg or '#ffffff'), quote=True)}; "
                        f"color: {escape(str(spec['row'].get('color', '#111827')), quote=True)}; "
                        f"font-size: {float(spec['row'].get('font_size', 10) or 10)}px;"
                    ),
                )
                for column in columns
            )
            body_rows.append(f"<tr>{cells}</tr>")
        body_html = f"<tbody>{''.join(body_rows)}</tbody>"
    else:
        empty = escape(str(spec.get("empty_message", "")))
        empty_height = max(row_height, available_height)
        empty_font_size = float(spec["row"].get("font_size", 10) or 10)
        body_html = (
            f'<tbody><tr><td colspan="{len(columns)}" '
            f'style="height: {empty_height}px; '
            f"color: #64748b; font-size: {empty_font_size}px; "
            'text-align: center;">'
            f"{empty}</td></tr></tbody>"
        )
    table_style = (
        "width: 100%; height: 100%; border-collapse: collapse; table-layout: fixed; "
        f"border: {border_width}px solid {border_color};"
    )
    wrapper_style = (
        f"{_position_style(x, y, width, height)} "
        f"background: {background}; border-radius: {radius}px; overflow: hidden;"
    )
    object_id = escape(obj.id, quote=True)
    return (
        f'<div class="slim-report-object slim-report-table" data-slim-object="{object_id}" '
        f'style="{wrapper_style}">'
        f'<table style="{table_style}">{colgroup}{header_html}{body_html}</table>'
        "</div>"
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


def _table_cell(value: object, *, align: str, style: str, tag: str = "td") -> str:
    text_align = escape(align if align in {"left", "center", "right"} else "left", quote=True)
    return (
        f'<{tag} style="box-sizing: border-box; padding: 2px 6px; overflow: hidden; '
        f'text-overflow: ellipsis; white-space: nowrap; text-align: {text_align}; {style}">'
        f"{escape(str(value if value is not None else ''))}</{tag}>"
    )


def _table_cell_value(
    column: dict[str, object],
    row: dict[str, object],
    data_path: str,
    context: RenderContext,
) -> str:
    binding = str(column.get("binding", "") or column.get("field", "") or column.get("id", ""))
    value = get_row_value(row, binding, data_path)
    if value in ("", None):
        value = get_value_by_path(context.data, binding)
    return "" if value is None else str(value)


def _column_width_percent(column: dict[str, object], columns: list[dict[str, object]]) -> float:
    total = sum(max(float(item.get("width", 0) or 0), 0) for item in columns)
    if total <= 0:
        return 100 / max(len(columns), 1)
    return max(float(column.get("width", 0) or 0), 0) * 100 / total


def _table_spec(obj: RenderObject) -> dict[str, object]:
    properties = obj.properties or {}
    columns = properties.get("columns")
    if not isinstance(columns, list) or not columns:
        columns = [
            {
                "id": "column_1",
                "label": "Column 1",
                "binding": "column_1",
                "width": 120,
                "align": "left",
            },
            {
                "id": "column_2",
                "label": "Column 2",
                "binding": "column_2",
                "width": 120,
                "align": "left",
            },
            {
                "id": "column_3",
                "label": "Column 3",
                "binding": "column_3",
                "width": 120,
                "align": "left",
            },
        ]
    return {
        "data_path": str(properties.get("data_path") or properties.get("binding") or ""),
        "columns": [_normalize_table_column(column, index) for index, column in enumerate(columns)],
        "header": {
            "visible": True,
            "height": 24,
            "background_color": "#e5e7eb",
            "color": "#111827",
            "font_size": 10,
            "bold": True,
            **_dict_value(properties.get("header")),
        },
        "row": {
            "height": 22,
            "background_color": "#ffffff",
            "alternate_background_color": "#f9fafb",
            "color": "#111827",
            "font_size": 10,
            **_dict_value(properties.get("row")),
        },
        "border": {
            "width": 1,
            "color": "#d1d5db",
            **_dict_value(properties.get("border")),
        },
        "empty_message": str(properties.get("empty_message", "")),
    }


def _normalize_table_column(column: object, index: int) -> dict[str, object]:
    mapping = _dict_value(column)
    binding = str(
        mapping.get("binding") or mapping.get("field") or mapping.get("id") or f"column_{index + 1}"
    )
    label = mapping.get("label") or binding.replace("_", " ").title() or f"Column {index + 1}"
    return {
        "id": str(mapping.get("id") or binding or f"column_{index + 1}"),
        "label": str(label),
        "binding": binding,
        "width": float(mapping.get("width", 120) or 120),
        "align": str(mapping.get("align", "left") or "left"),
    }


def _dict_value(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, dict) else {}


def _is_transparent(value: object) -> bool:
    return str(value or "").strip().lower() in {"", "none", "transparent"}


def _position_style(x: float, y: float, width: float, height: float) -> str:
    return f"left: {x}px; top: {y}px; width: {width}px; height: {height}px;"


def _horizontal_flex_align(value: str) -> str:
    if value == "center":
        return "center"
    if value == "right":
        return "flex-end"
    return "flex-start"


def _detail_repeat(context: RenderContext) -> dict[str, Any] | None:
    detail = next((band for band in context.bands if band.id == "detail"), None)
    if not detail or not detail.repeat.get("enabled") or not detail.repeat.get("data_path"):
        return None
    return detail.repeat


def _empty_message_html(context: RenderContext, repeat: dict[str, Any]) -> str:
    detail = next((band for band in context.bands if band.id == "detail"), None)
    top = float(getattr(detail, "y", 0) or 0) + 8
    message = escape(str(repeat.get("empty_message", "No records")))
    return (
        '<div class="slim-report-object" '
        f'style="left: 12px; top: {top}px; width: 240px; height: 18px; '
        'color: #64748b; font: 700 12px Arial, sans-serif;">'
        f"{message}</div>"
    )


def _vertical_flex_align(value: str) -> str:
    if value == "middle":
        return "center"
    if value == "bottom":
        return "flex-end"
    return "flex-start"
