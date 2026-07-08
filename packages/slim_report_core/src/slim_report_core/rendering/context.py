"""Shared rendering context and normalization helpers."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from ..exceptions import ReportValidationError
from ..formula import evaluate_condition, evaluate_formula_result
from ..models import Band, Object, Page
from ..report import Report

CSS_DPI = 96.0
POINTS_PER_INCH = 72.0
_TEXT_BINDING_PATTERN = re.compile(r"\{\{\s*(.*?)\s*\}\}")
_MISSING = object()

PAGE_SIZES = {
    "letter": {
        "px": (612.0, 792.0),
        "pt": (8.5 * POINTS_PER_INCH, 11.0 * POINTS_PER_INCH),
    },
    "legal": {
        "px": (612.0, 1008.0),
        "pt": (8.5 * POINTS_PER_INCH, 14.0 * POINTS_PER_INCH),
    },
    "a4": {
        "px": (595.0, 842.0),
        "pt": (210.0 * POINTS_PER_INCH / 25.4, 297.0 * POINTS_PER_INCH / 25.4),
    },
}

TEXT_STYLE_DEFAULTS: dict[str, Any] = {
    "font_family": "Arial",
    "font_size": 12,
    "bold": False,
    "italic": False,
    "underline": False,
    "color": "#111827",
    "background_color": "transparent",
    "align": "left",
    "vertical_align": "top",
    "line_height": 1.2,
}

RECTANGLE_STYLE_DEFAULTS: dict[str, Any] = {
    "border_width": 1,
    "border_color": "#111827",
    "background_color": "transparent",
    "border_radius": 0,
}

LINE_STYLE_DEFAULTS: dict[str, Any] = {
    "stroke_width": 1,
    "stroke_color": "#111827",
}

IMAGE_STYLE_DEFAULTS: dict[str, Any] = {
    "object_fit": "contain",
    "opacity": 1,
    "border_radius": 0,
    "border_width": 0,
    "border_color": "#000000",
    "background_color": "transparent",
}

TABLE_STYLE_DEFAULTS: dict[str, Any] = {
    "background_color": "#ffffff",
    "border_radius": 0,
    "overflow": "hidden",
}

BARCODE_STYLE_DEFAULTS: dict[str, Any] = {
    "foreground_color": "#111827",
    "background_color": "#ffffff",
    "font_size": 8,
}

QRCODE_STYLE_DEFAULTS: dict[str, Any] = {
    "foreground_color": "#111827",
    "background_color": "#ffffff",
}

UNIT_TO_PX = {
    "px": 1.0,
    "pt": CSS_DPI / POINTS_PER_INCH,
    "in": CSS_DPI,
    "mm": CSS_DPI / 25.4,
    "cm": CSS_DPI / 2.54,
}

UNIT_TO_PT = {
    "px": POINTS_PER_INCH / CSS_DPI,
    "pt": 1.0,
    "in": POINTS_PER_INCH,
    "mm": POINTS_PER_INCH / 25.4,
    "cm": POINTS_PER_INCH / 2.54,
}


@dataclass(frozen=True)
class RenderPage:
    """Resolved page dimensions for rendering."""

    size: str
    orientation: str
    unit: str
    width_px: float
    height_px: float
    width_pt: float
    height_pt: float
    background_color: str
    transparent: bool


@dataclass(frozen=True)
class RenderObject:
    """Normalized renderable report object."""

    id: str
    type: str
    x: float
    y: float
    width: float
    height: float
    text: str = ""
    binding: str = ""
    formula: str = ""
    formula_mode: bool = False
    conditions: list[dict[str, Any]] = field(default_factory=list)
    style: dict[str, Any] = field(default_factory=dict)
    band: str = "detail"
    locked: bool = False
    z_index: int = 0
    visible: bool = True
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RenderBand:
    """Normalized report band region."""

    id: str
    type: str
    name: str
    y: float
    height: float
    background_color: str = "transparent"
    visible: bool = True
    locked: bool = False
    repeat: dict[str, Any] = field(default_factory=dict)
    group: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RenderContext:
    """Normalized inputs for report rendering."""

    report: Report
    data: Mapping[str, Any]
    page: RenderPage
    bands: list[RenderBand]
    objects: list[RenderObject]
    title: str


def create_render_context(report: Report, data: Mapping[str, Any] | None = None) -> RenderContext:
    """Normalize a report domain model and data into a render context."""
    if not isinstance(report, Report):
        raise ReportValidationError("Renderer expects a Report domain model.")

    page = resolve_page(report.page)
    bands = normalize_bands(report.bands, page)
    objects = [normalize_object(item) for item in report.objects]
    objects.sort(key=lambda item: item.z_index)

    return RenderContext(
        report=report,
        data=data or {},
        page=page,
        bands=bands,
        objects=objects,
        title=resolve_title(report),
    )


def resolve_page(page: Page) -> RenderPage:
    """Resolve page size, orientation, and dimensions."""
    size = str(getattr(page, "size", "") or "").lower()
    unit = str(getattr(page, "unit", "px")).lower()
    orientation = str(getattr(page, "orientation", "portrait")).lower()

    if orientation not in {"portrait", "landscape"}:
        raise ReportValidationError(f"Unsupported page orientation: {orientation}.")

    width = float(getattr(page, "width", 0) or 0)
    height = float(getattr(page, "height", 0) or 0)
    if width < 0 or height < 0 or not math.isfinite(width) or not math.isfinite(height):
        raise ReportValidationError("Page width and height must be valid positive numbers.")
    if width > 0 and height > 0:
        width_px = convert_unit(width, unit, "px")
        height_px = convert_unit(height, unit, "px")
        width_pt = convert_unit(width, unit, "pt")
        height_pt = convert_unit(height, unit, "pt")
    elif size:
        if size not in PAGE_SIZES:
            raise ReportValidationError(f"Unsupported page size: {size}.")
        width_px, height_px = PAGE_SIZES[size]["px"]
        width_pt, height_pt = PAGE_SIZES[size]["pt"]
    else:
        width = float(getattr(page, "width", 8.5))
        height = float(getattr(page, "height", 11.0))
        width_px = convert_unit(width, unit, "px")
        height_px = convert_unit(height, unit, "px")
        width_pt = convert_unit(width, unit, "pt")
        height_pt = convert_unit(height, unit, "pt")
        size = "custom"

    if orientation == "landscape" and width_px < height_px:
        width_px, height_px = height_px, width_px
        width_pt, height_pt = height_pt, width_pt
    elif orientation == "portrait" and width_px > height_px:
        width_px, height_px = height_px, width_px
        width_pt, height_pt = height_pt, width_pt

    return RenderPage(
        size=size,
        orientation=orientation,
        unit=unit,
        width_px=width_px,
        height_px=height_px,
        width_pt=width_pt,
        height_pt=height_pt,
        background_color=str(getattr(page, "background_color", "#ffffff") or "#ffffff"),
        transparent=bool(getattr(page, "transparent", False)),
    )


def normalize_object(obj: Object) -> RenderObject:
    """Normalize a domain object for rendering."""
    if not isinstance(obj, Object):
        raise ReportValidationError("Renderer expects report objects from the Report model.")

    properties = _mapping(getattr(obj, "properties", {}))
    style = _style(obj, properties)
    binding = getattr(obj, "binding", None)
    binding_expression = getattr(binding, "expression", None)
    if binding_expression is None:
        binding_expression = properties.get(
            "binding",
            properties.get("field", properties.get("expression", "")),
        )

    x = float(getattr(obj, "x", 0))
    y = float(getattr(obj, "y", 0))
    width = float(getattr(obj, "width", 0))
    height = float(getattr(obj, "height", 0))
    if not all(math.isfinite(value) for value in (x, y, width, height)):
        raise ReportValidationError(
            f"Report object {getattr(obj, 'id', '')} has invalid coordinates."
        )
    if width < 0 or height < 0:
        raise ReportValidationError(
            f"Report object {getattr(obj, 'id', '')} has invalid dimensions."
        )

    band = (
        getattr(obj, "band_id", None)
        or properties.get("band")
        or properties.get("band_id")
        or "detail"
    )

    return RenderObject(
        id=_required_attr(obj, "id", "Report object"),
        type=_required_attr(obj, "type", "Report object"),
        x=x,
        y=y,
        width=width,
        height=height,
        text=str(getattr(obj, "text", "") or properties.get("text", "")),
        binding=str(binding_expression or ""),
        formula=str(properties.get("formula", getattr(obj, "formula", "")) or ""),
        formula_mode=_bool(properties.get("formula_mode", getattr(obj, "formula_mode", False))),
        conditions=_conditions(properties.get("conditions", getattr(obj, "conditions", []))),
        style=style,
        band=str(band),
        locked=_bool(properties.get("locked", getattr(obj, "locked", False))),
        z_index=int(getattr(obj, "z_index", 0)),
        visible=bool(getattr(obj, "visible", True)),
        properties=dict(properties),
    )


def normalize_bands(bands: list[Band], page: RenderPage) -> list[RenderBand]:
    """Normalize report bands, creating a compatibility detail band when absent."""
    if not bands:
        return [
            RenderBand(
                id="detail",
                type="detail",
                name="Detail",
                y=0,
                height=page.height_px,
            )
        ]
    normalized = [_normalize_band(item, page) for item in bands]
    return _recalculate_standard_bands(normalized, page)


def _normalize_band(band: Band, page: RenderPage) -> RenderBand:
    names = {
        "page_header": "Page Header",
        "detail": "Detail",
        "page_footer": "Page Footer",
    }
    band_type = str(getattr(band, "type", "") or getattr(band, "id", "") or "detail")
    band_id = str(getattr(band, "id", "") or band_type)
    return RenderBand(
        id=band_id,
        type=band_type,
        name=str(getattr(band, "name", None) or names.get(band_type, band_id)),
        y=float(getattr(band, "y", 0) or 0),
        height=max(float(getattr(band, "height", page.height_px) or page.height_px), 0),
        background_color=str(getattr(band, "background_color", "transparent") or "transparent"),
        visible=bool(getattr(band, "visible", True)),
        locked=bool(getattr(band, "locked", False)),
        repeat=dict(getattr(band, "repeat", {}) or {}),
        group=dict(getattr(band, "group", {}) or {}),
    )


def _recalculate_standard_bands(bands: list[RenderBand], page: RenderPage) -> list[RenderBand]:
    by_id = {band.id: band for band in bands}
    header = by_id.get("page_header")
    detail = by_id.get("detail")
    footer = by_id.get("page_footer")
    if not header or not detail or not footer:
        return bands
    page_height = page.height_px
    min_detail = min(80.0, page_height)
    header_height = max(0.0, min(header.height, page_height - min_detail))
    footer_height = max(0.0, min(footer.height, page_height - header_height - min_detail))
    group_header_height = sum(
        band.height for band in bands if band.type == "group_header" and band.visible
    )
    group_footer_height = sum(
        band.height for band in bands if band.type == "group_footer" and band.visible
    )
    detail_height = max(
        min_detail,
        page_height - header_height - footer_height - group_header_height - group_footer_height,
    )
    group_header_y = header_height
    detail_y = header_height + group_header_height
    group_footer_y = detail_y + detail_height
    replacements = {
        "page_header": RenderBand(**{**header.__dict__, "y": 0.0, "height": header_height}),
        "detail": RenderBand(**{**detail.__dict__, "y": detail_y, "height": detail_height}),
        "page_footer": RenderBand(
            **{
                **footer.__dict__,
                "y": group_footer_y + group_footer_height,
                "height": footer_height,
            }
        ),
    }
    resolved: list[RenderBand] = []
    for band in bands:
        if band.id in replacements:
            resolved.append(replacements[band.id])
        elif band.type == "group_header":
            resolved.append(RenderBand(**{**band.__dict__, "y": group_header_y}))
            group_header_y += band.height
        elif band.type == "group_footer":
            resolved.append(RenderBand(**{**band.__dict__, "y": group_footer_y}))
            group_footer_y += band.height
        else:
            resolved.append(band)
    return resolved


def resolve_title(report: Report) -> str:
    """Resolve a report title from report metadata."""
    return str(report.metadata.title)


def convert_unit(value: float, source_unit: str, target_unit: str) -> float:
    """Convert scalar dimensions between supported units."""
    source = source_unit.lower()
    target = target_unit.lower()
    if target == "px":
        return value * _unit_factor(source, UNIT_TO_PX)
    if target == "pt":
        return value * _unit_factor(source, UNIT_TO_PT)
    raise ReportValidationError(f"Unsupported target unit: {target_unit}.")


def object_px(obj: RenderObject, unit: str) -> tuple[float, float, float, float]:
    """Return object coordinates converted to CSS pixels."""
    return (
        convert_unit(obj.x, unit, "px"),
        convert_unit(obj.y, unit, "px"),
        convert_unit(obj.width, unit, "px"),
        convert_unit(obj.height, unit, "px"),
    )


def object_pt(obj: RenderObject, unit: str) -> tuple[float, float, float, float]:
    """Return object coordinates converted to PDF points."""
    return (
        convert_unit(obj.x, unit, "pt"),
        convert_unit(obj.y, unit, "pt"),
        convert_unit(obj.width, unit, "pt"),
        convert_unit(obj.height, unit, "pt"),
    )


def resolve_object_value(obj: RenderObject, data: Mapping[str, Any]) -> str:
    """Resolve display text for text-like render objects."""
    if obj.type == "text":
        return resolve_binding_text(obj.text, data)
    if obj.type == "field":
        return resolve_field_object_value(obj, data)
    return ""


def resolve_repeated_object_value(
    obj: RenderObject,
    data: Mapping[str, Any],
    row: Mapping[str, Any],
    repeat_data_path: str,
) -> str:
    """Resolve display text for a repeated-row render object."""
    if obj.type == "text":
        return resolve_binding_text(obj.text, data, row=row, repeat_data_path=repeat_data_path)
    if obj.type != "field":
        return ""
    return resolve_field_object_value(obj, data, row=row, repeat_data_path=repeat_data_path)


def resolve_grouped_object_value(
    obj: RenderObject,
    data: Mapping[str, Any],
    row: Mapping[str, Any] | None = None,
    repeat_data_path: str = "",
) -> str:
    """Resolve text/field values against group, row, then global data."""
    if obj.type == "text":
        return resolve_binding_text(obj.text, data, row=row, repeat_data_path=repeat_data_path)
    if obj.type != "field":
        return ""
    return resolve_field_object_value(obj, data, row=row, repeat_data_path=repeat_data_path)


def resolve_field_object_value(
    obj: RenderObject,
    data: Mapping[str, Any],
    *,
    row: Mapping[str, Any] | None = None,
    repeat_data_path: str = "",
) -> str:
    """Resolve a field object using formula mode first when enabled."""
    if obj.formula_mode and obj.formula.strip():
        result = evaluate_formula_result(
            obj.formula,
            data,
            resolver=lambda identifier: resolve_binding(
                identifier,
                data,
                row=row,
                repeat_data_path=repeat_data_path,
            ),
        )
        if result.ok:
            return value_to_text(result.value)
        if not obj.binding:
            return ""
    return value_to_text(
        resolve_binding(obj.binding, data, row=row, repeat_data_path=repeat_data_path)
    )


def resolve_bound_object_value(
    obj: RenderObject,
    data: Mapping[str, Any],
    row: Mapping[str, Any] | None = None,
    repeat_data_path: str = "",
) -> str:
    """Resolve a binding-capable non-field object with a value fallback."""
    if obj.binding:
        value = resolve_binding(obj.binding, data, row=row, repeat_data_path=repeat_data_path)
        if value not in ("", None):
            return value_to_text(value)
    value = obj.properties.get("value", "")
    return "" if value is None else str(value)


def object_with_conditional_style(
    obj: RenderObject,
    data: Mapping[str, Any],
) -> RenderObject | None:
    """Return an object with conditional style applied, or None when hidden."""
    resolved = apply_conditional_styles(obj, data)
    if resolved["hidden"]:
        return None
    if resolved["style"] == obj.style:
        return obj
    return RenderObject(**{**obj.__dict__, "style": resolved["style"]})


def apply_conditional_styles(
    obj: RenderObject,
    data: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate object conditions and return the merged style and hide action."""
    style = dict(obj.style)
    hidden = False
    if not obj.conditions:
        return {"style": style, "hidden": hidden}
    row = data.get("__slim_row__") if isinstance(data, Mapping) else None
    repeat_data_path = str(
        data.get("__slim_repeat_path__", "") if isinstance(data, Mapping) else ""
    )
    for condition in obj.conditions:
        if not bool(condition.get("enabled", True)):
            continue
        expression = str(condition.get("condition", "") or "").strip()
        if not expression:
            continue
        matched = evaluate_condition(
            expression,
            data,
            resolver=lambda identifier: resolve_binding(
                identifier,
                data,
                row=row if isinstance(row, Mapping) else None,
                repeat_data_path=repeat_data_path,
            ),
        )
        if not matched:
            continue
        condition_style = condition.get("style")
        if isinstance(condition_style, Mapping):
            style.update(dict(condition_style))
        action = condition.get("action", "")
        if isinstance(action, Mapping):
            action = action.get("type", action.get("name", ""))
        if str(action or "").lower() == "hide":
            hidden = True
    return {"style": style, "hidden": hidden}


def resolve_binding_text(
    text: str,
    data: Mapping[str, Any],
    *,
    row: Mapping[str, Any] | None = None,
    repeat_data_path: str = "",
) -> str:
    """Resolve ``{{ path }}`` markers using aggregate/system-aware binding resolution."""

    def replace(match: re.Match[str]) -> str:
        return value_to_text(
            resolve_binding(
                match.group(1),
                data,
                row=row,
                repeat_data_path=repeat_data_path,
            )
        )

    return _TEXT_BINDING_PATTERN.sub(replace, str(text or ""))


def resolve_binding(
    binding: str,
    data: Mapping[str, Any],
    *,
    row: Mapping[str, Any] | None = None,
    repeat_data_path: str = "",
) -> Any:
    """Resolve a simple path binding with system, group, report, row, then data precedence."""
    path = _strip_binding(binding)
    if not path:
        return ""

    value = resolve_system_binding(path, data)
    if value is not _MISSING:
        return value

    value = resolve_group_binding(path, data)
    if value is not _MISSING:
        return value

    value = resolve_report_binding(path, data)
    if value is not _MISSING:
        return value

    current_row = row
    if current_row is None and isinstance(data, Mapping):
        maybe_row = data.get("__slim_row__")
        current_row = maybe_row if isinstance(maybe_row, Mapping) else None
    if current_row is not None:
        row_value = get_row_value(current_row, path, repeat_data_path or _repeat_path(data))
        if row_value not in ("", None):
            return row_value

    value = get_value_by_path(data, path)
    if value is not None:
        return value

    return ""


def resolve_system_binding(binding: str, data: Mapping[str, Any]) -> Any:
    """Resolve page/date/time system bindings."""
    if binding == "date.today":
        return date.today().isoformat()
    if binding == "datetime.now":
        return datetime.now().strftime("%Y-%m-%d %H:%M")
    if binding in {"page.number", "page.index", "page.total_pages", "page.count"}:
        page = data.get("__slim_page__") if isinstance(data, Mapping) else None
        if isinstance(page, Mapping):
            keys = {
                "page.number": "number",
                "page.index": "index",
                "page.total_pages": "total_pages",
                "page.count": "count",
            }
            key = keys[binding]
            return page.get(key, "")
        return ""
    return _MISSING


def resolve_group_binding(binding: str, data: Mapping[str, Any]) -> Any:
    """Resolve group metadata and aggregate bindings."""
    group = data.get("__slim_group__") if isinstance(data, Mapping) else None
    if not isinstance(group, Mapping):
        return _MISSING
    field = str(group.get("field", "") or "")
    key = group.get("key", "")
    rows = group.get("rows", [])
    group_rows = rows if isinstance(rows, list) else []
    if binding in {field, "group", "group.key", "group.value"}:
        return key
    if binding == "group.field":
        return field
    if binding == "group.count":
        return aggregate_count(group_rows) if group_rows else int(group.get("count", 0) or 0)
    prefix = "group."
    if not binding.startswith(prefix):
        return _MISSING
    operation, aggregate_field = _aggregate_operation_and_field(binding[len(prefix) :])
    if operation is None:
        return _MISSING
    return _aggregate_rows(group_rows, operation, aggregate_field)


def resolve_report_binding(binding: str, data: Mapping[str, Any]) -> Any:
    """Resolve report-wide aggregates over array paths."""
    prefix = "report."
    if not binding.startswith(prefix):
        return _MISSING
    remainder = binding[len(prefix) :]
    operation, path = _first_path_segment(remainder)
    if operation not in {"count", "sum", "avg", "min", "max"} or not path:
        return _MISSING
    if operation == "count":
        return aggregate_count(get_array_by_path(data, path))
    array_path, field = _split_report_aggregate_path(data, path)
    if not array_path or not field:
        return ""
    rows = get_array_by_path(data, array_path)
    if not rows and get_value_by_path(data, array_path) is None:
        return ""
    return _aggregate_rows(rows, operation, field)


def to_number(value: Any) -> float | None:
    """Return a float for numeric-like values, ignoring invalid values."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def aggregate_count(rows: list[Any]) -> int:
    return len(rows)


def aggregate_sum(rows: list[Any], field: str) -> Any:
    return _format_number(sum(_numeric_values(rows, field)))


def aggregate_avg(rows: list[Any], field: str) -> Any:
    values = _numeric_values(rows, field)
    if not values:
        return ""
    return _format_number(sum(values) / len(values))


def aggregate_min(rows: list[Any], field: str) -> Any:
    values = _numeric_values(rows, field)
    return "" if not values else _format_number(min(values))


def aggregate_max(rows: list[Any], field: str) -> Any:
    values = _numeric_values(rows, field)
    return "" if not values else _format_number(max(values))


def context_with_page_numbers(
    context: RenderContext,
    page_number: int,
    total_pages: int,
) -> RenderContext:
    """Return context with page system variables available to binding resolution."""
    return RenderContext(
        report=context.report,
        data={
            **dict(context.data),
            "__slim_page__": {
                "number": page_number,
                "index": max(page_number - 1, 0),
                "total_pages": total_pages,
                "count": total_pages,
            },
        },
        page=context.page,
        bands=context.bands,
        objects=context.objects,
        title=context.title,
    )


def get_group_value(data: Mapping[str, Any], binding: str) -> Any:
    group = data.get("__slim_group__") if isinstance(data, Mapping) else None
    if not isinstance(group, Mapping):
        return None
    path = str(binding or "").strip()
    key = group.get("key", "")
    field = str(group.get("field", "") or "")
    if path in {field, "group", "group.key", "group.value"}:
        return key
    if path in {"count", "group.count"}:
        return group.get("count", 0)
    if path == "group.field":
        return field
    return None


def value_to_text(value: Any) -> str:
    if value is None or value is _MISSING:
        return ""
    return str(value)


def _strip_binding(binding: str) -> str:
    value = str(binding or "").strip()
    match = _TEXT_BINDING_PATTERN.fullmatch(value)
    if match:
        return match.group(1).strip()
    return value


def _repeat_path(data: Mapping[str, Any]) -> str:
    return str(data.get("__slim_repeat_path__", "") if isinstance(data, Mapping) else "")


def _aggregate_operation_and_field(value: str) -> tuple[str | None, str]:
    operation, field = _first_path_segment(value)
    if operation not in {"sum", "avg", "min", "max"} or not field:
        return None, ""
    return operation, field


def _first_path_segment(value: str) -> tuple[str, str]:
    operation, separator, remainder = str(value or "").partition(".")
    return operation, remainder if separator else ""


def _split_report_aggregate_path(data: Mapping[str, Any], path: str) -> tuple[str, str]:
    parts = str(path or "").split(".")
    for index in range(len(parts) - 1, 0, -1):
        array_path = ".".join(parts[:index])
        if get_array_by_path(data, array_path):
            return array_path, ".".join(parts[index:])
    if len(parts) >= 2:
        return ".".join(parts[:-1]), parts[-1]
    return "", ""


def _aggregate_rows(rows: list[Any], operation: str, field: str) -> Any:
    if operation == "sum":
        return aggregate_sum(rows, field)
    if operation == "avg":
        return aggregate_avg(rows, field)
    if operation == "min":
        return aggregate_min(rows, field)
    if operation == "max":
        return aggregate_max(rows, field)
    return ""


def _numeric_values(rows: list[Any], field: str) -> list[float]:
    numbers: list[float] = []
    for row in rows:
        row_data = row if isinstance(row, Mapping) else {}
        number = to_number(get_value_by_path(row_data, field))
        if number is not None:
            numbers.append(number)
    return numbers


def _format_number(value: float) -> int | float:
    if float(value).is_integer():
        return int(value)
    return round(value, 6)


def _conditions(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            continue
        condition = {
            "id": str(item.get("id") or f"condition_{index + 1}"),
            "enabled": bool(item.get("enabled", True)),
            "condition": str(item.get("condition", "") or ""),
            "style": dict(item.get("style")) if isinstance(item.get("style"), Mapping) else {},
        }
        if "action" in item:
            condition["action"] = item["action"]
        normalized.append(condition)
    return normalized


def get_value_by_path(data: Any, path: str) -> Any:
    """Return a nested value from dict/list data using dot and [] path syntax."""
    value = data
    for token in _path_tokens(path):
        if value is None:
            return None
        if token == "[]":
            value = value[0] if isinstance(value, list) and value else None
        elif token.startswith("[") and token.endswith("]"):
            try:
                index = int(token[1:-1])
            except ValueError:
                return None
            value = value[index] if isinstance(value, list) and index < len(value) else None
        elif isinstance(value, Mapping):
            value = value.get(token)
        else:
            value = getattr(value, token, None)
    return value


def get_array_by_path(data: Any, path: str) -> list[Any]:
    """Return an array at path, or an empty list."""
    value = get_value_by_path(data, path)
    return value if isinstance(value, list) else []


def get_row_value(row: Mapping[str, Any], binding: str, repeat_data_path: str = "") -> Any:
    """Resolve row-relative or matching array-child binding against one row."""
    path = str(binding or "").strip()
    repeat_path = str(repeat_data_path or "").strip()
    if repeat_path and path.startswith(f"{repeat_path}[]."):
        path = path[len(f"{repeat_path}[].") :]
    value = get_value_by_path(row, path)
    return "" if value is None else value


def _group_expression_data(data: Mapping[str, Any]) -> dict[str, Any]:
    resolved = dict(data)
    group = data.get("__slim_group__") if isinstance(data, Mapping) else None
    if isinstance(group, Mapping):
        resolved["group"] = {
            "key": group.get("key", ""),
            "value": group.get("key", ""),
            "count": group.get("count", 0),
            "field": group.get("field", ""),
        }
        field = str(group.get("field", "") or "")
        if field and field not in resolved:
            resolved[field] = group.get("key", "")
    return resolved


def _style(obj: Any, properties: Mapping[str, Any]) -> dict[str, Any]:
    object_type = str(getattr(obj, "type", "text") or "text")
    style = default_style_for_type(object_type)
    explicit = dict(_mapping(properties.get("style")))
    style.update(explicit)
    explicit_style = explicit
    object_style = getattr(obj, "style", None)
    if hasattr(object_style, "resolved_values"):
        explicit_style = object_style.resolved_values()
        style.update(explicit_style)
    else:
        explicit_style = dict(_mapping(getattr(object_style, "values", {})))
        style.update(explicit_style)

    for key in _STYLE_KEYS:
        if key in properties and key not in explicit_style:
            style[key] = properties[key]

    if "fill_color" in style and "background_color" not in explicit_style:
        style["background_color"] = style["fill_color"]
    if "line_width" in style and "stroke_width" not in explicit_style:
        style["stroke_width"] = style["line_width"]
    if object_type == "line" and "border_color" in style and "stroke_color" not in explicit_style:
        style["stroke_color"] = style["border_color"]
    style["bold"] = _bool(style.get("bold", False))
    style["italic"] = _bool(style.get("italic", False))
    style["underline"] = _bool(style.get("underline", False))
    return style


def _path_tokens(path: str) -> list[str]:
    tokens: list[str] = []
    for part in str(path or "").strip().split("."):
        name = part
        indexes: list[str] = []
        while "[" in name and "]" in name:
            before, after = name.split("[", 1)
            index, rest = after.split("]", 1)
            if before:
                tokens.append(before)
            tokens.append("[]" if index == "" else f"[{index}]")
            name = rest
            indexes.append(index)
        if name:
            tokens.append(name)
    return tokens


def default_style_for_type(object_type: str) -> dict[str, Any]:
    """Return renderer defaults shared by HTML/PDF and the designer canvas."""
    if object_type == "rectangle":
        return dict(RECTANGLE_STYLE_DEFAULTS)
    if object_type == "line":
        return dict(LINE_STYLE_DEFAULTS)
    if object_type == "image":
        return dict(IMAGE_STYLE_DEFAULTS)
    if object_type == "table":
        return dict(TABLE_STYLE_DEFAULTS)
    if object_type == "barcode":
        return dict(BARCODE_STYLE_DEFAULTS)
    if object_type == "qrcode":
        return dict(QRCODE_STYLE_DEFAULTS)
    return dict(TEXT_STYLE_DEFAULTS)


_STYLE_KEYS = (
    "align",
    "background_color",
    "bold",
    "border_color",
    "border_width",
    "color",
    "fill_color",
    "font_family",
    "font_size",
    "foreground_color",
    "italic",
    "line_height",
    "line_width",
    "object_fit",
    "opacity",
    "border_radius",
    "stroke_color",
    "stroke_width",
    "underline",
    "vertical_align",
)


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _required_attr(obj: Any, key: str, context: str) -> str:
    value = getattr(obj, key, None)
    if value is None or str(value).strip() == "":
        raise ReportValidationError(f"{context} requires a non-empty {key}.")
    return str(value)


def _unit_factor(unit: str, factors: Mapping[str, float]) -> float:
    if unit not in factors:
        raise ReportValidationError(f"Unsupported unit: {unit}.")
    return factors[unit]
