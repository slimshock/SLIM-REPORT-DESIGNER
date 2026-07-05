"""Dataclass models for the framework-agnostic report template."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Any

from .constants import (
    DEFAULT_MARGIN_BOTTOM,
    DEFAULT_MARGIN_LEFT,
    DEFAULT_MARGIN_RIGHT,
    DEFAULT_MARGIN_TOP,
    DEFAULT_PAGE_HEIGHT,
    DEFAULT_PAGE_ORIENTATION,
    DEFAULT_PAGE_UNIT,
    DEFAULT_PAGE_WIDTH,
    DEFAULT_REPORT_VERSION,
)
from .exceptions import ReportValidationError
from .schema import validate_template_mapping
from .utils import ensure_mapping


@dataclass
class ReportMetadata:
    """Human-readable metadata for a report template."""

    title: str = "Untitled Report"
    description: str | None = None
    author: str | None = None
    tags: list[str] = field(default_factory=list)
    custom: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> ReportMetadata:
        if data is None:
            return cls()

        mapping = ensure_mapping(data, context="Report metadata")
        return cls(
            title=str(mapping.get("title", "Untitled Report")),
            description=_optional_str(mapping.get("description")),
            author=_optional_str(mapping.get("author")),
            tags=[str(tag) for tag in mapping.get("tags", [])],
            custom=dict(mapping.get("custom", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReportPage:
    """Page settings for a report template."""

    width: float = DEFAULT_PAGE_WIDTH
    height: float = DEFAULT_PAGE_HEIGHT
    unit: str = DEFAULT_PAGE_UNIT
    orientation: str = DEFAULT_PAGE_ORIENTATION
    margin_top: float = DEFAULT_MARGIN_TOP
    margin_right: float = DEFAULT_MARGIN_RIGHT
    margin_bottom: float = DEFAULT_MARGIN_BOTTOM
    margin_left: float = DEFAULT_MARGIN_LEFT

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> ReportPage:
        if data is None:
            return cls()

        mapping = ensure_mapping(data, context="Report page")
        return cls(
            width=float(mapping.get("width", DEFAULT_PAGE_WIDTH)),
            height=float(mapping.get("height", DEFAULT_PAGE_HEIGHT)),
            unit=str(mapping.get("unit", DEFAULT_PAGE_UNIT)),
            orientation=str(mapping.get("orientation", DEFAULT_PAGE_ORIENTATION)),
            margin_top=float(mapping.get("margin_top", DEFAULT_MARGIN_TOP)),
            margin_right=float(mapping.get("margin_right", DEFAULT_MARGIN_RIGHT)),
            margin_bottom=float(mapping.get("margin_bottom", DEFAULT_MARGIN_BOTTOM)),
            margin_left=float(mapping.get("margin_left", DEFAULT_MARGIN_LEFT)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReportObject:
    """Renderable object within a report template."""

    id: str
    type: str
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    band_id: str | None = None
    z_index: int = 0
    visible: bool = True
    properties: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ReportObject:
        mapping = ensure_mapping(data, context="Report object")
        return cls(
            id=_required_str(mapping, "id", context="Report object"),
            type=_required_str(mapping, "type", context="Report object"),
            x=float(mapping.get("x", 0.0)),
            y=float(mapping.get("y", 0.0)),
            width=float(mapping.get("width", 0.0)),
            height=float(mapping.get("height", 0.0)),
            band_id=_optional_str(mapping.get("band_id")),
            z_index=int(mapping.get("z_index", 0)),
            visible=bool(mapping.get("visible", True)),
            properties=dict(mapping.get("properties", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReportBand:
    """Layout band for grouping report objects."""

    id: str
    type: str
    height: float = 0.0
    properties: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ReportBand:
        mapping = ensure_mapping(data, context="Report band")
        return cls(
            id=_required_str(mapping, "id", context="Report band"),
            type=_required_str(mapping, "type", context="Report band"),
            height=float(mapping.get("height", 0.0)),
            properties=dict(mapping.get("properties", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReportAsset:
    """External or embedded asset referenced by a report template."""

    id: str
    type: str
    source: str
    name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ReportAsset:
        mapping = ensure_mapping(data, context="Report asset")
        return cls(
            id=_required_str(mapping, "id", context="Report asset"),
            type=_required_str(mapping, "type", context="Report asset"),
            source=_required_str(mapping, "source", context="Report asset"),
            name=_optional_str(mapping.get("name")),
            metadata=dict(mapping.get("metadata", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReportTemplate:
    """Serializable report template model."""

    version: str = DEFAULT_REPORT_VERSION
    metadata: ReportMetadata = field(default_factory=ReportMetadata)
    page: ReportPage = field(default_factory=ReportPage)
    objects: list[ReportObject] = field(default_factory=list)
    bands: list[ReportBand] = field(default_factory=list)
    assets: list[ReportAsset] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ReportTemplate:
        mapping = ensure_mapping(data, context="Report template")
        validate_template_mapping(mapping)
        return cls(
            version=str(mapping["version"]),
            metadata=ReportMetadata.from_dict(mapping["metadata"]),
            page=ReportPage.from_dict(mapping["page"]),
            objects=[ReportObject.from_dict(item) for item in mapping["objects"]],
            bands=[ReportBand.from_dict(item) for item in mapping["bands"]],
            assets=[ReportAsset.from_dict(item) for item in mapping["assets"]],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "metadata": self.metadata.to_dict(),
            "page": self.page.to_dict(),
            "objects": [item.to_dict() for item in self.objects],
            "bands": [item.to_dict() for item in self.bands],
            "assets": [item.to_dict() for item in self.assets],
        }


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _required_str(mapping: Mapping[str, Any], key: str, *, context: str) -> str:
    value = mapping.get(key)
    if value is None or str(value).strip() == "":
        raise ReportValidationError(f"{context} requires a non-empty {key}.")
    return str(value)
