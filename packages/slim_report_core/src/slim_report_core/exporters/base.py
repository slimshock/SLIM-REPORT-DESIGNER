"""Base exporter classes and shared layout helpers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from typing import Any

from ..exceptions import ExporterError
from ..models import ReportObject
from ..report import Report
from ..widgets import WidgetRegistry, create_default_widget_registry

PAGE_SIZES: dict[str, tuple[float, float, str]] = {
    "letter": (8.5, 11.0, "in"),
    "a4": (210.0, 297.0, "mm"),
}

UNIT_TO_POINTS: dict[str, float] = {
    "pt": 1.0,
    "px": 0.75,
    "in": 72.0,
    "mm": 72.0 / 25.4,
    "cm": 72.0 / 2.54,
}


@dataclass
class PageLayout:
    """Resolved page dimensions in points."""

    width: float
    height: float
    unit: str
    source_unit: str
    orientation: str


@dataclass
class BaseExporter(ABC):
    """Base class for report exporters."""

    widget_registry: WidgetRegistry = field(default_factory=create_default_widget_registry)
    page_size: str | None = None
    orientation: str | None = None

    @abstractmethod
    def export(self, report: Report, data: Any = None, context: Any = None) -> Any:
        """Export a report."""

    def get_widget(self, obj: ReportObject):
        """Return a registered widget for an object or raise an exporter error."""
        widget = self.widget_registry.get(obj.type)
        if widget is None:
            raise ExporterError(f"No widget registered for report object type: {obj.type}.")
        return widget

    def resolve_page_layout(self, report: Report) -> PageLayout:
        """Resolve page size and orientation to points."""
        page = report.page
        width = page.width
        height = page.height
        source_unit = page.unit

        if self.page_size is not None:
            width, height, source_unit = _page_size_values(self.page_size)

        orientation = (self.orientation or page.orientation).lower()
        if orientation not in {"portrait", "landscape"}:
            raise ExporterError(f"Unsupported page orientation: {orientation}.")

        width_pt = convert_unit(width, source_unit, "pt")
        height_pt = convert_unit(height, source_unit, "pt")
        if orientation == "landscape" and width_pt < height_pt:
            width_pt, height_pt = height_pt, width_pt
        if orientation == "portrait" and width_pt > height_pt:
            width_pt, height_pt = height_pt, width_pt

        return PageLayout(
            width=width_pt,
            height=height_pt,
            unit="pt",
            source_unit=source_unit,
            orientation=orientation,
        )


def convert_unit(value: float, source_unit: str, target_unit: str) -> float:
    """Convert a scalar between supported page units."""
    source = source_unit.lower()
    target = target_unit.lower()
    if source not in UNIT_TO_POINTS:
        raise ExporterError(f"Unsupported source unit: {source_unit}.")
    if target not in UNIT_TO_POINTS:
        raise ExporterError(f"Unsupported target unit: {target_unit}.")
    return value * UNIT_TO_POINTS[source] / UNIT_TO_POINTS[target]


def object_to_points(obj: ReportObject, source_unit: str) -> ReportObject:
    """Return a copy of an object with coordinates converted to points."""
    return replace(
        obj,
        x=convert_unit(obj.x, source_unit, "pt"),
        y=convert_unit(obj.y, source_unit, "pt"),
        width=convert_unit(obj.width, source_unit, "pt"),
        height=convert_unit(obj.height, source_unit, "pt"),
    )


def render_context(context: Any, layout: PageLayout) -> dict[str, Any]:
    """Create renderer context with internal page metadata."""
    if isinstance(context, dict):
        resolved = dict(context)
    else:
        resolved = {}
        if context is not None:
            resolved["value"] = context

    resolved["_slim_report_page_width_pt"] = layout.width
    resolved["_slim_report_page_height_pt"] = layout.height
    resolved["_slim_report_page_orientation"] = layout.orientation
    return resolved


def _page_size_values(page_size: str) -> tuple[float, float, str]:
    key = page_size.lower()
    if key not in PAGE_SIZES:
        raise ExporterError(f"Unsupported page size: {page_size}.")
    return PAGE_SIZES[key]
