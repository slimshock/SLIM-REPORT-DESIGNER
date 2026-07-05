"""Shared rendering context and normalization helpers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from ..exceptions import ReportValidationError
from ..expressions import resolve_expression, resolve_text

CSS_DPI = 96.0
POINTS_PER_INCH = 72.0

PAGE_SIZES = {
    "letter": {
        "px": (8.5 * CSS_DPI, 11.0 * CSS_DPI),
        "pt": (8.5 * POINTS_PER_INCH, 11.0 * POINTS_PER_INCH),
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


@dataclass(frozen=True)
class RenderContext:
    """Normalized inputs for report rendering."""

    template: Mapping[str, Any]
    data: Mapping[str, Any]
    page: RenderPage
    objects: list[RenderObject]
    title: str


def create_render_context(template: Any, data: Mapping[str, Any] | None = None) -> RenderContext:
    """Normalize a report template and data into a render context."""
    template_dict = normalize_template(template)
    page = resolve_page(template_dict.get("page", {}))
    objects = [
        normalize_object(item)
        for item in template_dict.get("objects", [])
        if isinstance(item, Mapping)
    ]
    objects.sort(key=lambda item: item.z_index)

    return RenderContext(
        template=template_dict,
        data=data or {},
        page=page,
        objects=objects,
        title=resolve_title(template_dict),
    )


def normalize_template(template: Any) -> Mapping[str, Any]:
    """Convert supported template inputs into a mapping."""
    if isinstance(template, Mapping):
        return template
    if hasattr(template, "to_dict") and callable(template.to_dict):
        return template.to_dict()
    raise ReportValidationError(
        "Renderer expects a report template mapping or object with to_dict()."
    )


def resolve_page(page: Any) -> RenderPage:
    """Resolve page size, orientation, and dimensions."""
    page_mapping = page if isinstance(page, Mapping) else {}
    size = str(page_mapping.get("size", "") or "").lower()
    unit = str(page_mapping.get("unit", "px")).lower()
    orientation = str(page_mapping.get("orientation", "portrait")).lower()

    if orientation not in {"portrait", "landscape"}:
        raise ReportValidationError(f"Unsupported page orientation: {orientation}.")

    if size:
        if size not in PAGE_SIZES:
            raise ReportValidationError(f"Unsupported page size: {size}.")
        width_px, height_px = PAGE_SIZES[size]["px"]
        width_pt, height_pt = PAGE_SIZES[size]["pt"]
    else:
        width = float(page_mapping.get("width", 8.5))
        height = float(page_mapping.get("height", 11.0))
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
    )


def normalize_object(obj: Mapping[str, Any]) -> RenderObject:
    """Normalize object shapes used by templates and dataclasses."""
    properties = _mapping(obj.get("properties"))
    style = _style(obj, properties)
    object_type = _required_str(obj, "type", "Report object")

    return RenderObject(
        id=_required_str(obj, "id", "Report object"),
        type=object_type,
        x=float(obj.get("x", 0)),
        y=float(obj.get("y", 0)),
        width=float(obj.get("width", 0)),
        height=float(obj.get("height", 0)),
        text=str(obj.get("text", properties.get("text", ""))),
        binding=str(
            obj.get(
                "binding",
                properties.get(
                    "binding",
                    properties.get("field", properties.get("expression", "")),
                ),
            )
        ),
        style=style,
        z_index=int(obj.get("z_index", 0)),
        visible=bool(obj.get("visible", True)),
    )


def resolve_title(template: Mapping[str, Any]) -> str:
    """Resolve a report title from template metadata."""
    metadata = template.get("metadata")
    if isinstance(metadata, Mapping):
        return str(metadata.get("title", "Untitled Report"))
    return "Untitled Report"


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


def _style(obj: Mapping[str, Any], properties: Mapping[str, Any]) -> dict[str, Any]:
    style = dict(_mapping(properties.get("style")))
    style.update(_mapping(obj.get("style")))

    for key in (
        "align",
        "bold",
        "border_color",
        "border_width",
        "color",
        "fill_color",
        "font_family",
        "font_size",
        "line_width",
        "stroke_width",
    ):
        if key in properties and key not in style:
            style[key] = properties[key]
    return style


def _mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _required_str(mapping: Mapping[str, Any], key: str, context: str) -> str:
    value = mapping.get(key)
    if value is None or str(value).strip() == "":
        raise ReportValidationError(f"{context} requires a non-empty {key}.")
    return str(value)


def _unit_factor(unit: str, factors: Mapping[str, float]) -> float:
    if unit not in factors:
        raise ReportValidationError(f"Unsupported unit: {unit}.")
    return factors[unit]
