"""ReportLab PDF renderer for report templates."""

from __future__ import annotations

import base64
from io import BytesIO
from typing import Any

from ..assets.resolver import ResolvedImageSource, resolve_image_source
from ..exceptions import ExporterError, ReportValidationError
from ..report import Report
from .context import (
    RenderContext,
    RenderObject,
    context_with_page_numbers,
    convert_unit,
    create_render_context,
    get_array_by_path,
    get_row_value,
    get_value_by_path,
    object_pt,
    object_with_conditional_style,
    resolve_bound_object_value,
    resolve_grouped_object_value,
    resolve_object_value,
    resolve_repeated_object_value,
)
from .pagination import build_render_pages
from .qrcode import QR_GRID_SIZE, qr_module_matrix


def render_pdf(
    report: Report,
    data: dict[str, Any] | None = None,
    *,
    asset_provider: Any | None = None,
    asset_resolver: Any | None = None,
) -> bytes:
    """Render a report domain model and data as PDF bytes."""
    canvas_class = _load_canvas()
    context = create_render_context(
        report,
        data,
        asset_provider=asset_provider,
        asset_resolver=asset_resolver,
    )
    buffer = BytesIO()
    canvas = canvas_class(buffer, pagesize=(context.page.width_pt, context.page.height_pt))
    _apply_pdf_metadata(canvas, report)
    pages = build_render_pages(context)
    for page_index, page in enumerate(pages):
        page_number = page_index + 1
        _render_page_background(canvas, context)
        for band in page.bands:
            _render_band(canvas, band, context)
        for obj, object_context in page.objects:
            render_pdf_object(
                canvas,
                obj,
                context_with_page_numbers(object_context, page_number, len(pages)),
            )
        if page_index < len(pages) - 1:
            canvas.showPage()
    canvas.save()
    return buffer.getvalue()


def _apply_pdf_metadata(canvas: Any, report: Report) -> None:
    settings = getattr(getattr(report, "page", None), "print", {}) or {}
    title = str(
        settings.get("pdf_title") or getattr(report.metadata, "title", "") or "Untitled Report"
    )
    author = str(
        settings.get("pdf_author")
        or getattr(report.metadata, "author", "")
        or "Slim Report Designer"
    )
    subject = str(settings.get("pdf_subject") or getattr(report.metadata, "description", "") or "")
    metadata = {
        "setTitle": title,
        "setAuthor": author,
        "setCreator": "Slim Report Designer",
    }
    if subject:
        metadata["setSubject"] = subject
    for method_name, value in metadata.items():
        setter = getattr(canvas, method_name, None)
        if callable(setter):
            setter(value)


def _render_page_background(canvas: Any, context: RenderContext) -> None:
    if context.page.transparent:
        return
    _set_fill_color(canvas, context.page.background_color)
    canvas.rect(0, 0, context.page.width_pt, context.page.height_pt, stroke=0, fill=1)


def render_pdf_object(canvas: Any, obj: RenderObject, context: RenderContext) -> None:
    """Render one normalized report object onto a ReportLab canvas."""
    if not obj.visible:
        return
    resolved_obj = object_with_conditional_style(obj, context.data)
    if resolved_obj is None:
        return
    obj = resolved_obj
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
    if obj.type == "table":
        _render_table(canvas, obj, context)
        return
    if obj.type == "barcode":
        _render_barcode(canvas, obj, context)
        return
    if obj.type == "qrcode":
        _render_qrcode(canvas, obj, context)
        return
    raise ReportValidationError(f"Unsupported report object type: {obj.type}.")


def pdf_render_objects(context: RenderContext) -> list[tuple[RenderObject, RenderContext]]:
    repeat = _detail_repeat(context)
    if not repeat:
        return [(obj, context) for obj in context.objects]
    data_path = str(repeat.get("data_path", ""))
    rows = get_array_by_path(context.data, data_path)
    detail_objects = [obj for obj in context.objects if obj.band == "detail"]
    rendered = [(obj, context) for obj in context.objects if obj.band != "detail"]
    if not rows:
        return rendered
    row_height = float(repeat.get("row_height", 22) or 22)
    for row_index, row in enumerate(rows):
        row_data = row if isinstance(row, dict) else {}
        row_context = context_with_row(context, row_data, data_path)
        for obj in detail_objects:
            repeated = RenderObject(
                **{
                    **obj.__dict__,
                    "id": f"{obj.id}__row_{row_index}",
                    "y": obj.y + (row_index * row_height),
                }
            )
            rendered.append((repeated, row_context))
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
    value = (
        resolve_grouped_object_value(obj, context.data)
        if _group_context(context) is not None
        else resolve_object_value(obj, context.data)
    )
    _draw_text(canvas, obj, context, value)


def _render_field(canvas: Any, obj: RenderObject, context: RenderContext) -> None:
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
    _draw_text(canvas, obj, context, value)


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
    border_width = _style_length_pt(
        style.get("border_width", style.get("stroke_width", 1)),
        context,
    )
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

    resolved_source = _resolved_image_source(obj, context)
    reader = _image_reader(resolved_source)
    if reader is None:
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
        return


def _render_barcode(canvas: Any, obj: RenderObject, context: RenderContext) -> None:
    x, y, width, height = object_pt(obj, context.page.unit)
    value = _object_value(obj, context)
    style = obj.style
    background = style.get("background_color", "#ffffff")
    foreground = style.get("foreground_color", "#111827")
    font_size = _font_size_pt(style.get("font_size", 8), context)
    show_text = bool(obj.properties.get("show_text", True))
    text_height = font_size + 4 if show_text else 0
    bar_height = max(height - text_height, 4)

    if not _is_transparent(background):
        _set_fill_color(canvas, background)
        canvas.rect(x, _pdf_y(context, y + height), width, height, stroke=0, fill=1)

    if not value:
        _draw_barcode_placeholder(canvas, x, y, width, height, context, "Barcode")
        return

    try:
        from reportlab.graphics.barcode.code128 import Code128

        barcode = Code128(value, barHeight=bar_height, humanReadable=False)
        if hasattr(barcode, "barFillColor"):
            barcode.barFillColor = _hex_color(foreground)
        scale_x = width / max(float(getattr(barcode, "width", width) or width), 1)
        scale_y = bar_height / max(float(getattr(barcode, "height", bar_height) or bar_height), 1)
        canvas.saveState()
        canvas.translate(x, _pdf_y(context, y + bar_height))
        canvas.scale(scale_x, scale_y)
        barcode.drawOn(canvas, 0, 0)
        canvas.restoreState()
    except Exception:
        _draw_barcode_placeholder(canvas, x, y, width, bar_height, context, value)

    if show_text:
        canvas.setFont("Helvetica", font_size)
        _set_fill_color(canvas, foreground)
        text_width = canvas.stringWidth(value, "Helvetica", font_size)
        text_x = x + max((width - text_width) / 2, 0)
        canvas.drawString(text_x, _pdf_y(context, y + bar_height + font_size), value)


def _render_qrcode(canvas: Any, obj: RenderObject, context: RenderContext) -> None:
    x, y, width, height = object_pt(obj, context.page.unit)
    value = _object_value(obj, context) or "QR Code"
    style = obj.style
    background = style.get("background_color", "#ffffff")
    foreground = style.get("foreground_color", "#111827")
    size = min(width, height)
    qr_x = x + max((width - size) / 2, 0)
    qr_y = y + max((height - size) / 2, 0)

    if not _is_transparent(background):
        _set_fill_color(canvas, background)
        canvas.rect(x, _pdf_y(context, y + height), width, height, stroke=0, fill=1)

    _draw_qr_placeholder(canvas, qr_x, qr_y, size, context, foreground, background, value)


def _draw_barcode_placeholder(
    canvas: Any,
    x: float,
    y: float,
    width: float,
    height: float,
    context: RenderContext,
    label: str,
) -> None:
    _set_fill_color(canvas, "#111827")
    cursor = x
    pattern = (2, 1, 1, 3, 2, 2, 1, 1, 3, 1)
    index = 0
    while cursor < x + width:
        bar_width = pattern[index % len(pattern)]
        canvas.rect(cursor, _pdf_y(context, y + height), bar_width, height, stroke=0, fill=1)
        cursor += bar_width + 2
        index += 1
    canvas.setFont("Helvetica", 7)
    _set_fill_color(canvas, "#64748b")
    canvas.drawString(x + 2, _pdf_y(context, y + height + 8), str(label)[:40])


def _draw_qr_placeholder(
    canvas: Any,
    x: float,
    y: float,
    size: float,
    context: RenderContext,
    foreground: Any,
    background: Any,
    value: str,
) -> None:
    if not _is_transparent(background):
        _set_fill_color(canvas, background)
        canvas.rect(x, _pdf_y(context, y + size), size, size, stroke=0, fill=1)
    cell = size / QR_GRID_SIZE
    _set_fill_color(canvas, foreground)
    for row, modules in enumerate(qr_module_matrix(value)):
        for col, enabled in enumerate(modules):
            if enabled:
                canvas.rect(
                    x + (col * cell),
                    _pdf_y(context, y + ((row + 1) * cell)),
                    cell,
                    cell,
                    stroke=0,
                    fill=1,
                )


def _render_table(canvas: Any, obj: RenderObject, context: RenderContext) -> None:
    x, y, width, height = object_pt(obj, context.page.unit)
    spec = _table_spec(obj)
    columns = spec["columns"]
    rows_override = obj.properties.get("__slim_table_rows__")
    row_offset = int(obj.properties.get("__slim_table_row_offset__", 0) or 0)
    rows = (
        rows_override
        if isinstance(rows_override, list)
        else get_array_by_path(context.data, spec["data_path"])
    )
    row_height = _table_length_pt(spec["row"].get("height", 22), context)
    header_height = (
        _table_length_pt(spec["header"].get("height", 24), context)
        if spec["header"].get("visible", True)
        else 0
    )
    border_width = _table_length_pt(spec["border"].get("width", 1), context)
    col_widths = _table_column_widths(columns, width)
    table_top = y
    table_bottom = y + height
    cursor_y = table_top

    background = obj.style.get("background_color", "#ffffff")
    if not _is_transparent(background):
        _set_fill_color(canvas, background)
        canvas.rect(x, _pdf_y(context, table_bottom), width, height, stroke=0, fill=1)

    if spec["header"].get("visible", True) and header_height > 0:
        _draw_table_row(
            canvas,
            context,
            x,
            cursor_y,
            col_widths,
            header_height,
            [str(column.get("label", "")) for column in columns],
            fill_color=spec["header"].get("background_color", "#e5e7eb"),
            text_color=spec["header"].get("color", "#111827"),
            font_size=spec["header"].get("font_size", 10),
            bold=bool(spec["header"].get("bold", True)),
            aligns=[str(column.get("align", "left")) for column in columns],
            border_color=spec["border"].get("color", "#d1d5db"),
            border_width=border_width,
        )
        cursor_y += header_height

    available_height = max(table_bottom - cursor_y, 0)
    max_rows = max(0, int(available_height // max(row_height, 1)))
    for row_index, row in enumerate(rows[:max_rows]):
        row_data = row if isinstance(row, dict) else {}
        fill = (
            spec["row"].get("alternate_background_color")
            if (row_offset + row_index) % 2 == 1
            else spec["row"].get("background_color", "#ffffff")
        )
        values = [
            _table_cell_value(column, row_data, str(spec["data_path"]), context)
            for column in columns
        ]
        _draw_table_row(
            canvas,
            context,
            x,
            cursor_y,
            col_widths,
            row_height,
            values,
            fill_color=fill or "#ffffff",
            text_color=spec["row"].get("color", "#111827"),
            font_size=spec["row"].get("font_size", 10),
            bold=False,
            aligns=[str(column.get("align", "left")) for column in columns],
            border_color=spec["border"].get("color", "#d1d5db"),
            border_width=border_width,
        )
        cursor_y += row_height

    if not rows:
        _draw_table_row(
            canvas,
            context,
            x,
            cursor_y,
            [width],
            max(row_height, available_height),
            [str(spec.get("empty_message", ""))],
            fill_color=spec["row"].get("background_color", "#ffffff"),
            text_color="#64748b",
            font_size=spec["row"].get("font_size", 10),
            bold=False,
            aligns=["center"],
            border_color=spec["border"].get("color", "#d1d5db"),
            border_width=border_width,
        )

    if border_width > 0:
        canvas.setLineWidth(border_width)
        _set_stroke_color(canvas, spec["border"].get("color", "#d1d5db"))
        canvas.rect(x, _pdf_y(context, y + height), width, height, stroke=1, fill=0)


def _draw_table_row(
    canvas: Any,
    context: RenderContext,
    x: float,
    top_y: float,
    col_widths: list[float],
    height: float,
    values: list[str],
    *,
    fill_color: Any,
    text_color: Any,
    font_size: Any,
    bold: bool,
    aligns: list[str],
    border_color: Any,
    border_width: float,
) -> None:
    cursor_x = x
    font_name = "Helvetica-Bold" if bold else "Helvetica"
    resolved_font_size = _font_size_pt(font_size, context)
    for index, col_width in enumerate(col_widths):
        if not _is_transparent(fill_color):
            _set_fill_color(canvas, fill_color)
            canvas.rect(
                cursor_x,
                _pdf_y(context, top_y + height),
                col_width,
                height,
                stroke=0,
                fill=1,
            )
        if border_width > 0:
            canvas.setLineWidth(border_width)
            _set_stroke_color(canvas, border_color)
            canvas.rect(
                cursor_x,
                _pdf_y(context, top_y + height),
                col_width,
                height,
                stroke=1,
                fill=0,
            )
        value = values[index] if index < len(values) else ""
        canvas.setFont(font_name, resolved_font_size)
        _set_fill_color(canvas, text_color)
        padding = 4
        text_width = canvas.stringWidth(value, font_name, resolved_font_size)
        align = aligns[index] if index < len(aligns) else "left"
        text_x = cursor_x + padding
        if align == "center":
            text_x = cursor_x + max((col_width - text_width) / 2, padding)
        elif align == "right":
            text_x = cursor_x + max(col_width - text_width - padding, padding)
        baseline = _pdf_y(context, top_y + (height / 2) - (resolved_font_size / 2)) - 1
        canvas.drawString(text_x, baseline, str(value))
        cursor_x += col_width


def _table_length_pt(value: Any, context: RenderContext) -> float:
    length = float(value or 0)
    if context.page.unit == "px":
        return convert_unit(length, "px", "pt")
    return length


def _table_column_widths(columns: list[dict[str, Any]], table_width: float) -> list[float]:
    raw_widths = [max(float(column.get("width", 0) or 0), 0) for column in columns]
    total = sum(raw_widths)
    if total <= 0:
        return [table_width / max(len(columns), 1)] * len(columns)
    return [table_width * raw / total for raw in raw_widths]


def _table_cell_value(
    column: dict[str, Any],
    row: dict[str, Any],
    data_path: str,
    context: RenderContext,
) -> str:
    binding = str(column.get("binding", "") or column.get("field", "") or column.get("id", ""))
    value = get_row_value(row, binding, data_path)
    if value in ("", None):
        value = get_value_by_path(context.data, binding)
    return "" if value is None else str(value)


def _table_spec(obj: RenderObject) -> dict[str, Any]:
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


def _normalize_table_column(column: Any, index: int) -> dict[str, Any]:
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


def _dict_value(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _image_reader(source: str | ResolvedImageSource) -> Any | None:
    content: bytes | None = None
    if isinstance(source, ResolvedImageSource):
        content = source.content
        source = source.source
    if not source:
        if content is None:
            return None
    if source.startswith(("http://", "https://")):
        return None
    try:
        from reportlab.lib.utils import ImageReader
    except ImportError:
        return None
    if content is not None:
        try:
            return ImageReader(BytesIO(content))
        except Exception:
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


def _image_source(value: Any) -> str:
    text = str(value or "").strip()
    if text.lower() in {"", "none", "null", "undefined"}:
        return ""
    if text.startswith("{{") and text.endswith("}}"):
        return ""
    return text


def _resolved_image_source(obj: RenderObject, context: RenderContext) -> ResolvedImageSource:
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
            prefer_url=False,
            prefer_bytes=True,
        )
    return resolve_image_source(
        source=source,
        asset_id=asset_id,
        asset_provider=context.asset_provider,
        prefer_url=False,
        prefer_bytes=True,
    )


def _image_asset_id(obj: RenderObject) -> str:
    return str(
        obj.properties.get("assetId")
        or obj.properties.get("asset_id")
        or obj.properties.get("asset")
        or ""
    ).strip()


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


def _detail_repeat(context: RenderContext) -> dict[str, Any] | None:
    detail = next((band for band in context.bands if band.id == "detail"), None)
    if not detail or not detail.repeat.get("enabled") or not detail.repeat.get("data_path"):
        return None
    return detail.repeat
