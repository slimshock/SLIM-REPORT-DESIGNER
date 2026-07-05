"""Shared rendering context and normalization helpers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from ..exceptions import ReportValidationError
from ..expressions import resolve_expression, resolve_text
from ..models import Object, Page
from ..report import Report

CSS_DPI = 96.0
POINTS_PER_INCH = 72.0

PAGE_SIZES = {
    "letter": {
        "px": (8.5 * CSS_DPI, 11.0 * CSS_DPI),
        "pt": (8.5 * POINTS_PER_INCH, 11.0 * POINTS_PER_INCH),
    },
    "legal": {
        "px": (8.5 * CSS_DPI, 14.0 * CSS_DPI),
        "pt": (8.5 * POINTS_PER_INCH, 14.0 * POINTS_PER_INCH),
    },
    "a4": {
        "px": (210.0 * CSS_DPI / 25.4, 297.0 * CSS_DPI / 25.4),
        "pt": (210.0 * POINTS_PER_INCH / 25.4, 297.0 * POINTS_PER_INCH / 25.4),
    },
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
    style: dict[str, Any] = field(default_factory=dict)
    z_index: int = 0
    visible: bool = True
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RenderContext:
    """Normalized inputs for report rendering."""

    report: Report
    data: Mapping[str, Any]
    page: RenderPage
    objects: list[RenderObject]
    title: str


def create_render_context(report: Report, data: Mapping[str, Any] | None = None) -> RenderContext:
    """Normalize a report domain model and data into a render context."""
    if not isinstance(report, Report):
        raise ReportValidationError("Renderer expects a Report domain model.")

    page = resolve_page(report.page)
    objects = [normalize_object(item) for item in report.objects]
    objects.sort(key=lambda item: item.z_index)

    return RenderContext(
        report=report,
        data=data or {},
        page=page,
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

    return RenderObject(
        id=_required_attr(obj, "id", "Report object"),
        type=_required_attr(obj, "type", "Report object"),
        x=float(getattr(obj, "x", 0)),
        y=float(getattr(obj, "y", 0)),
        width=float(getattr(obj, "width", 0)),
        height=float(getattr(obj, "height", 0)),
        text=str(getattr(obj, "text", "") or properties.get("text", "")),
        binding=str(binding_expression or ""),
        style=style,
        z_index=int(getattr(obj, "z_index", 0)),
        visible=bool(getattr(obj, "visible", True)),
        properties=dict(properties),
    )


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
        return str(resolve_text(obj.text, data))
    if obj.type == "field":
        return str(resolve_expression(obj.binding, data))
    return ""


def _style(obj: Any, properties: Mapping[str, Any]) -> dict[str, Any]:
    style = dict(_mapping(properties.get("style")))
    object_style = getattr(obj, "style", None)
    if hasattr(object_style, "resolved_values"):
        style.update(object_style.resolved_values())
    else:
        style.update(_mapping(getattr(object_style, "values", {})))

    for key in (
        "align",
        "background_color",
        "bold",
        "border_color",
        "border_width",
        "color",
        "fill_color",
        "font_family",
        "font_size",
        "italic",
        "line_width",
        "object_fit",
        "opacity",
        "border_radius",
        "stroke_color",
        "stroke_width",
        "underline",
        "vertical_align",
    ):
        if key in properties and key not in style:
            style[key] = properties[key]
    return style


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
