"""Shared pagination helpers for report renderers."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .context import (
    RenderBand,
    RenderContext,
    RenderObject,
    get_array_by_path,
)

PAGINATION_DEFAULTS: dict[str, bool] = {
    "enabled": True,
    "repeat_page_header": True,
    "repeat_page_footer": True,
    "respect_margins": True,
}


@dataclass(frozen=True)
class RenderPagePlan:
    """Objects and bands to render on one output page."""

    index: int
    bands: list[RenderBand]
    objects: list[tuple[RenderObject, RenderContext]]


@dataclass(frozen=True)
class PaginationSummary:
    """Lightweight pagination counters for preview/export diagnostics."""

    page_count: int
    repeated_row_count: int
    table_row_count: int


def build_render_pages(context: RenderContext) -> list[RenderPagePlan]:
    """Build page-aware render plans for repeats and basic detail tables."""
    settings = get_pagination_settings(context)
    repeat = get_detail_repeat(context)
    table = first_paginated_table(context)
    if not settings["enabled"]:
        return [single_page_plan(context)]
    if repeat:
        return repeat_render_pages(context, repeat, settings)
    if table is not None:
        return table_render_pages(context, table, settings)
    return [single_page_plan(context)]


def pagination_summary(context: RenderContext, data: Any | None = None) -> PaginationSummary:
    """Return diagnostic counts using the same pagination logic as renderers."""
    data_context = context if data is None else context_with_data(context, data)
    pages = build_render_pages(data_context)
    repeat = get_detail_repeat(data_context)
    repeated_rows = 0
    if repeat:
        data_path = str(repeat.get("data_path", ""))
        repeated_rows = len(get_array_by_path(data_context.data, data_path))
    table_rows = sum(
        len(get_array_by_path(data_context.data, table_data_path(obj)))
        for obj in data_context.objects
        if obj.type == "table" and table_data_path(obj)
    )
    return PaginationSummary(
        page_count=max(len(pages), 1),
        repeated_row_count=repeated_rows,
        table_row_count=table_rows,
    )


def single_page_plan(context: RenderContext) -> RenderPagePlan:
    """Return a one-page plan that preserves legacy single-page expansion."""
    repeat = get_detail_repeat(context)
    if not repeat:
        return RenderPagePlan(0, list(context.bands), [(obj, context) for obj in context.objects])

    data_path = str(repeat.get("data_path", ""))
    rows = get_array_by_path(context.data, data_path)
    detail_objects = [obj for obj in context.objects if obj.band == "detail"]
    objects = [(obj, context) for obj in context.objects if obj.band != "detail"]
    if not rows:
        objects.append((empty_repeat_object(context, repeat), context))
        return RenderPagePlan(0, list(context.bands), objects)

    row_height = float(repeat.get("row_height", 22) or 22)
    for row_index, row in enumerate(rows):
        row_data = row if isinstance(row, dict) else {}
        row_context = context_with_row(context, row_data, data_path)
        for obj in detail_objects:
            objects.append((repeated_object(obj, row_index, row_index, row_height), row_context))
    return RenderPagePlan(0, list(context.bands), objects)


def repeat_render_pages(
    context: RenderContext,
    repeat: dict[str, Any],
    settings: dict[str, bool],
) -> list[RenderPagePlan]:
    """Build pages for a repeating Detail band."""
    data_path = str(repeat.get("data_path", ""))
    rows = get_array_by_path(context.data, data_path)
    detail_objects = [obj for obj in context.objects if obj.band == "detail"]
    row_height = float(repeat.get("row_height", 22) or 22)
    rows_per_page = repeat_rows_per_page(context, row_height, detail_objects)

    if not rows:
        objects = outside_objects_for_page(context, 0, settings)
        objects.append((empty_repeat_object(context, repeat), context))
        return [
            RenderPagePlan(
                0,
                bands_for_page(context, 0, settings),
                objects,
            )
        ]

    pages: list[RenderPagePlan] = []
    for page_index, start in enumerate(range(0, len(rows), rows_per_page)):
        page_rows = rows[start : start + rows_per_page]
        objects = outside_objects_for_page(context, page_index, settings)
        for local_index, row in enumerate(page_rows):
            row_data = row if isinstance(row, dict) else {}
            row_context = context_with_row(context, row_data, data_path)
            for obj in detail_objects:
                objects.append(
                    (
                        repeated_object(obj, start + local_index, local_index, row_height),
                        row_context,
                    )
                )
        pages.append(
            RenderPagePlan(page_index, bands_for_page(context, page_index, settings), objects)
        )
    return pages or [single_page_plan(context)]


def table_render_pages(
    context: RenderContext,
    table: RenderObject,
    settings: dict[str, bool],
) -> list[RenderPagePlan]:
    """Build pages for one basic array-bound Detail table."""
    data_path = table_data_path(table)
    rows = get_array_by_path(context.data, data_path)
    rows_per_page = table_rows_per_page(context, table)
    non_table_detail = [
        obj for obj in context.objects if obj.band == "detail" and obj.id != table.id
    ]
    if not rows:
        objects = outside_objects_for_page(context, 0, settings)
        objects.extend((obj, context) for obj in non_table_detail)
        objects.append((table, context))
        return [RenderPagePlan(0, bands_for_page(context, 0, settings), objects)]

    pages: list[RenderPagePlan] = []
    for page_index, start in enumerate(range(0, len(rows), rows_per_page)):
        page_rows = rows[start : start + rows_per_page]
        objects = outside_objects_for_page(context, page_index, settings)
        objects.extend((obj, context) for obj in non_table_detail)
        objects.append((table_page_object(context, table, page_index, start, page_rows), context))
        pages.append(
            RenderPagePlan(page_index, bands_for_page(context, page_index, settings), objects)
        )
    return pages or [single_page_plan(context)]


def repeat_rows_per_page(
    context: RenderContext,
    row_height: float,
    detail_objects: list[RenderObject],
) -> int:
    """Calculate repeating Detail rows that fit on one generated page."""
    if not detail_objects:
        return calculate_rows_per_page(row_height, get_available_detail_height(context))
    content_bottom = get_content_bottom(context)
    last_row_bottom = max(obj.y + obj.height for obj in detail_objects)
    available = max(content_bottom - last_row_bottom + row_height, row_height)
    return calculate_rows_per_page(row_height, available)


def table_rows_per_page(context: RenderContext, table: RenderObject) -> int:
    """Calculate basic table rows that fit in the table and above the footer."""
    top = table.y
    available = max(min(table.height, get_content_bottom(context) - top), 0)
    header_height = table_header_height(table)
    row_height = table_row_height(table)
    return calculate_rows_per_page(row_height, max(available - header_height, row_height))


def calculate_rows_per_page(row_height: float, available_height: float) -> int:
    """Return at least one row per page for positive row heights."""
    safe_row_height = max(float(row_height or 0), 1.0)
    safe_available = max(float(available_height or 0), safe_row_height)
    return max(1, math.floor(safe_available / safe_row_height))


def get_page_height(context: RenderContext) -> float:
    return context.page.height_px


def get_page_width(context: RenderContext) -> float:
    return context.page.width_px


def get_header_band(context: RenderContext) -> RenderBand | None:
    return next((band for band in context.bands if band.id == "page_header"), None)


def get_detail_band(context: RenderContext) -> RenderBand | None:
    return next((band for band in context.bands if band.id == "detail"), None)


def get_footer_band(context: RenderContext) -> RenderBand | None:
    return next((band for band in context.bands if band.id == "page_footer"), None)


def get_content_top(context: RenderContext) -> float:
    detail = get_detail_band(context)
    if detail:
        return detail.y
    return 0.0


def get_content_bottom(context: RenderContext) -> float:
    footer = get_footer_band(context)
    if footer:
        return footer.y
    detail = get_detail_band(context)
    if detail:
        return detail.y + detail.height
    return context.page.height_px


def get_available_detail_height(context: RenderContext) -> float:
    return max(get_content_bottom(context) - get_content_top(context), 0.0)


def get_pagination_settings(context: RenderContext) -> dict[str, bool]:
    raw = getattr(context.report.page, "pagination", {}) or {}
    return {
        key: bool(raw.get(key, default)) if isinstance(raw, dict) else default
        for key, default in PAGINATION_DEFAULTS.items()
    }


def get_detail_repeat(context: RenderContext) -> dict[str, Any] | None:
    detail = get_detail_band(context)
    if not detail or not detail.repeat.get("enabled") or not detail.repeat.get("data_path"):
        return None
    return detail.repeat


def first_paginated_table(context: RenderContext) -> RenderObject | None:
    for obj in context.objects:
        if obj.type != "table" or obj.band != "detail":
            continue
        if table_data_path(obj):
            return obj
    return None


def bands_for_page(
    context: RenderContext,
    page_index: int,
    settings: dict[str, bool],
) -> list[RenderBand]:
    bands: list[RenderBand] = []
    for band in context.bands:
        if band.id == "page_header" and page_index > 0 and not settings["repeat_page_header"]:
            continue
        if band.id == "page_footer" and page_index > 0 and not settings["repeat_page_footer"]:
            continue
        bands.append(band)
    return bands


def outside_objects_for_page(
    context: RenderContext,
    page_index: int,
    settings: dict[str, bool],
) -> list[tuple[RenderObject, RenderContext]]:
    objects: list[tuple[RenderObject, RenderContext]] = []
    for obj in context.objects:
        if obj.band == "detail":
            continue
        if obj.band == "page_header" and page_index > 0 and not settings["repeat_page_header"]:
            continue
        if obj.band == "page_footer" and page_index > 0 and not settings["repeat_page_footer"]:
            continue
        if obj.band not in {"page_header", "page_footer"} and page_index > 0:
            continue
        objects.append((obj, context))
    return objects


def repeated_object(
    obj: RenderObject,
    global_row_index: int,
    local_row_index: int,
    row_height: float,
) -> RenderObject:
    return RenderObject(
        **{
            **obj.__dict__,
            "id": f"{obj.id}__row_{global_row_index}",
            "y": obj.y + (local_row_index * row_height),
        }
    )


def empty_repeat_object(context: RenderContext, repeat: dict[str, Any]) -> RenderObject:
    detail = get_detail_band(context)
    return RenderObject(
        id="__slim_empty_repeat",
        type="text",
        x=12,
        y=(detail.y if detail else 0) + 8,
        width=240,
        height=18,
        text=str(repeat.get("empty_message", "No records")),
        style={
            "font_family": "Arial",
            "font_size": 12,
            "bold": True,
            "color": "#64748b",
            "background_color": "transparent",
        },
        band="detail",
    )


def table_page_object(
    context: RenderContext,
    table: RenderObject,
    page_index: int,
    row_offset: int,
    rows: list[Any],
) -> RenderObject:
    properties = {
        **dict(table.properties),
        "__slim_table_rows__": rows,
        "__slim_table_row_offset__": row_offset,
    }
    top = table.y if page_index == 0 else max(get_content_top(context), table.y)
    return RenderObject(
        **{
            **table.__dict__,
            "id": table.id if page_index == 0 else f"{table.id}__page_{page_index + 1}",
            "y": top,
            "properties": properties,
        }
    )


def context_with_row(context: RenderContext, row: dict[str, Any], data_path: str) -> RenderContext:
    return RenderContext(
        report=context.report,
        data={**dict(context.data), "__slim_row__": row, "__slim_repeat_path__": data_path},
        page=context.page,
        bands=context.bands,
        objects=context.objects,
        title=context.title,
    )


def context_with_data(context: RenderContext, data: Any) -> RenderContext:
    return RenderContext(
        report=context.report,
        data=data if isinstance(data, dict) else {},
        page=context.page,
        bands=context.bands,
        objects=context.objects,
        title=context.title,
    )


def table_data_path(obj: RenderObject) -> str:
    return str(obj.properties.get("data_path") or obj.properties.get("binding") or "")


def table_header_height(obj: RenderObject) -> float:
    header = obj.properties.get("header")
    if isinstance(header, dict) and header.get("visible", True) is False:
        return 0.0
    return float(header.get("height", 24) if isinstance(header, dict) else 24)


def table_row_height(obj: RenderObject) -> float:
    row = obj.properties.get("row")
    return float(row.get("height", 22) if isinstance(row, dict) else 22)
