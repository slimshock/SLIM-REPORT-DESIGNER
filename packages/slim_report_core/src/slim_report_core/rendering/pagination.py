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
    get_row_value,
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
        if get_group_header_band(context):
            return grouped_repeat_render_pages(context, repeat, settings)
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


@dataclass(frozen=True)
class RowGroup:
    """Rows grouped by one repeat field."""

    key: str
    rows: list[Any]
    field: str


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
        objects = outside_objects_for_page(
            context,
            0,
            settings,
            exclude_band_types={"group_header", "group_footer"},
        )
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


def grouped_repeat_render_pages(
    context: RenderContext,
    repeat: dict[str, Any],
    settings: dict[str, bool],
) -> list[RenderPagePlan]:
    """Build pages for a repeating Detail band grouped by one field."""
    data_path = str(repeat.get("data_path", ""))
    row_height = float(repeat.get("row_height", 22) or 22)
    rows = get_array_by_path(context.data, data_path)
    group_header = get_group_header_band(context)
    group_footer = get_group_footer_band(context)
    detail = get_detail_band(context)
    detail_y = detail.y if detail else get_content_top(context)
    flow_top = get_grouped_content_top(context, group_header)
    groups = sort_groups(
        group_rows(rows, get_group_field(context), data_path),
        str((group_header.group if group_header else {}).get("sort", "none")),
    )

    if not rows or not groups:
        objects = outside_objects_for_page(context, 0, settings)
        objects.append((empty_repeat_object(context, repeat), context))
        return [RenderPagePlan(0, bands_for_grouped_page(context, 0, settings), objects)]

    detail_objects = [obj for obj in context.objects if obj.band == "detail"]
    group_header_objects = [
        obj for obj in context.objects if group_header and obj.band == group_header.id
    ]
    group_footer_objects = [
        obj for obj in context.objects if group_footer and obj.band == group_footer.id
    ]
    pages: list[RenderPagePlan] = []
    page_index = 0
    cursor = flow_top
    objects = outside_objects_for_page(
        context,
        page_index,
        settings,
        exclude_band_types={"group_header", "group_footer"},
    )
    bands = bands_for_grouped_page(context, page_index, settings)

    def start_new_page() -> None:
        nonlocal page_index, cursor, objects, bands
        pages.append(RenderPagePlan(page_index, bands, objects))
        page_index += 1
        cursor = flow_top
        objects = outside_objects_for_page(
            context,
            page_index,
            settings,
            exclude_band_types={"group_header", "group_footer"},
        )
        bands = bands_for_grouped_page(context, page_index, settings)

    def ensure_space(height: float) -> None:
        if cursor > flow_top and cursor + height > get_content_bottom(context):
            start_new_page()

    for group in groups:
        group_context = context_with_group(context, group)
        header_height = group_header.height if group_header and group_header.visible else 0.0
        footer_height = group_footer.height if group_footer and group_footer.visible else 0.0
        if group_header and group_header.visible:
            ensure_space(header_height)
            bands.append(
                flow_band(group_header, cursor, f"__group_header_{page_index}_{len(pages)}")
            )
            for obj in group_header_objects:
                objects.append((flow_object(obj, cursor, group_header.y), group_context))
            cursor += header_height

        for row_index, row in enumerate(group.rows):
            ensure_space(row_height)
            if (
                row_index > 0
                and cursor == flow_top
                and group_header
                and group_header.visible
            ):
                bands.append(
                    flow_band(group_header, cursor, f"__group_header_{page_index}_{row_index}")
                )
                for obj in group_header_objects:
                    objects.append((flow_object(obj, cursor, group_header.y), group_context))
                cursor += header_height
                ensure_space(row_height)
            row_data = row if isinstance(row, dict) else {}
            row_context = context_with_row_group(context, row_data, data_path, group)
            for obj in detail_objects:
                objects.append(
                    (
                        flow_object(
                            obj,
                            cursor,
                            detail_y,
                            suffix=f"__group_{safe_suffix(group.key)}_row_{row_index}",
                        ),
                        row_context,
                    )
                )
            cursor += row_height

        if group_footer and group_footer.visible:
            ensure_space(footer_height)
            bands.append(
                flow_band(group_footer, cursor, f"__group_footer_{page_index}_{len(pages)}")
            )
            footer_context = context_with_group(context, group)
            for obj in group_footer_objects:
                objects.append((flow_object(obj, cursor, group_footer.y), footer_context))
            cursor += footer_height

    pages.append(RenderPagePlan(page_index, bands, objects))
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


def get_group_bands(context: RenderContext) -> list[RenderBand]:
    return [band for band in context.bands if band.type in {"group_header", "group_footer"}]


def get_group_header_band(context: RenderContext) -> RenderBand | None:
    return next((band for band in context.bands if band.type == "group_header"), None)


def get_group_footer_band(context: RenderContext) -> RenderBand | None:
    return next((band for band in context.bands if band.type == "group_footer"), None)


def get_group_field(context: RenderContext) -> str:
    header = get_group_header_band(context)
    return str((header.group if header else {}).get("field", ""))


def get_content_top(context: RenderContext) -> float:
    detail = get_detail_band(context)
    if detail:
        return detail.y
    return 0.0


def get_grouped_content_top(context: RenderContext, group_header: RenderBand | None) -> float:
    if group_header and group_header.visible:
        return group_header.y
    return get_content_top(context)


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


def bands_for_grouped_page(
    context: RenderContext,
    page_index: int,
    settings: dict[str, bool],
) -> list[RenderBand]:
    return [
        band
        for band in bands_for_page(context, page_index, settings)
        if band.type not in {"group_header", "group_footer", "detail"}
    ]


def outside_objects_for_page(
    context: RenderContext,
    page_index: int,
    settings: dict[str, bool],
    *,
    exclude_band_types: set[str] | None = None,
) -> list[tuple[RenderObject, RenderContext]]:
    objects: list[tuple[RenderObject, RenderContext]] = []
    excluded = exclude_band_types or set()
    band_types = {band.id: band.type for band in context.bands}
    for obj in context.objects:
        if obj.band == "detail":
            continue
        if band_types.get(obj.band) in excluded:
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


def flow_object(
    obj: RenderObject,
    cursor_y: float,
    band_y: float,
    *,
    suffix: str = "",
) -> RenderObject:
    return RenderObject(
        **{
            **obj.__dict__,
            "id": f"{obj.id}{suffix}" if suffix else obj.id,
            "y": cursor_y + (obj.y - band_y),
        }
    )


def flow_band(band: RenderBand, y: float, suffix: str) -> RenderBand:
    return RenderBand(**{**band.__dict__, "id": f"{band.id}{suffix}", "y": y})


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
        asset_provider=context.asset_provider,
        asset_resolver=context.asset_resolver,
    )


def context_with_group(context: RenderContext, group: RowGroup) -> RenderContext:
    return RenderContext(
        report=context.report,
        data={**dict(context.data), "__slim_group__": group_context_data(group)},
        page=context.page,
        bands=context.bands,
        objects=context.objects,
        title=context.title,
        asset_provider=context.asset_provider,
        asset_resolver=context.asset_resolver,
    )


def context_with_row_group(
    context: RenderContext,
    row: dict[str, Any],
    data_path: str,
    group: RowGroup,
) -> RenderContext:
    return RenderContext(
        report=context.report,
        data={
            **dict(context.data),
            "__slim_row__": row,
            "__slim_repeat_path__": data_path,
            "__slim_group__": group_context_data(group),
        },
        page=context.page,
        bands=context.bands,
        objects=context.objects,
        title=context.title,
        asset_provider=context.asset_provider,
        asset_resolver=context.asset_resolver,
    )


def group_context_data(group: RowGroup) -> dict[str, Any]:
    return {
        "key": group.key,
        "value": group.key,
        "count": len(group.rows),
        "field": group.field,
        "rows": group.rows,
    }


def context_with_data(context: RenderContext, data: Any) -> RenderContext:
    return RenderContext(
        report=context.report,
        data=data if isinstance(data, dict) else {},
        page=context.page,
        bands=context.bands,
        objects=context.objects,
        title=context.title,
        asset_provider=context.asset_provider,
        asset_resolver=context.asset_resolver,
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


def group_rows(rows: list[Any], field: str, data_path: str = "") -> list[RowGroup]:
    groups: list[RowGroup] = []
    by_key: dict[str, RowGroup] = {}
    for row in rows:
        row_data = row if isinstance(row, dict) else {}
        value = get_row_value(row_data, field, data_path) if field else ""
        key = "" if value is None else str(value)
        if key not in by_key:
            by_key[key] = RowGroup(key=key, rows=[], field=field)
            groups.append(by_key[key])
        by_key[key].rows.append(row)
    return groups


def sort_groups(groups: list[RowGroup], sort: str = "none") -> list[RowGroup]:
    if sort == "asc":
        return sorted(groups, key=lambda group: group.key)
    if sort == "desc":
        return sorted(groups, key=lambda group: group.key, reverse=True)
    return groups


def safe_suffix(value: str) -> str:
    suffix = "".join(char if char.isalnum() else "_" for char in value.lower()).strip("_")
    return suffix or "ungrouped"
