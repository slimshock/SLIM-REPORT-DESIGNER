"""Domain models for framework-agnostic reports."""

from __future__ import annotations

import copy
import uuid
from collections.abc import Iterator, Mapping
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any

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
from .exceptions import ReportObjectNotFoundError, ReportValidationError
from .schema import validate_template_mapping
from .utils import ensure_mapping

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

if TYPE_CHECKING:
    from .validation import ReportValidationResult


@dataclass
class Metadata:
    """Human-readable report metadata."""

    title: str = "Untitled Report"
    description: str | None = None
    author: str | None = None
    tags: list[str] = field(default_factory=list)
    custom: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> Metadata:
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

    def __call__(
        self,
        *,
        title: str | None = None,
        subtitle: str | None = None,
        description: str | None = None,
        author: str | None = None,
        tags: list[str] | None = None,
        **custom: Any,
    ) -> Metadata:
        """Update metadata values and return this metadata object.

        Calling without arguments returns the object unchanged.
        """
        if title is not None:
            self.title = title
        if subtitle is not None:
            self.custom["subtitle"] = subtitle
        if description is not None:
            self.description = description
        if author is not None:
            self.author = author
        if tags is not None:
            self.tags = list(tags)
        if custom:
            self.custom.update(custom)
        return self

    def clone(self) -> Metadata:
        """Return a deep clone of this metadata."""
        return Metadata(
            title=self.title,
            description=self.description,
            author=self.author,
            tags=list(self.tags),
            custom=copy.deepcopy(self.custom),
        )


@dataclass
class Margin:
    """Page margin values in the page unit."""

    top: float = DEFAULT_MARGIN_TOP
    right: float = DEFAULT_MARGIN_RIGHT
    bottom: float = DEFAULT_MARGIN_BOTTOM
    left: float = DEFAULT_MARGIN_LEFT

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> Margin:
        if data is None:
            return cls()

        mapping = ensure_mapping(data, context="Report margin")
        return cls(
            top=float(mapping.get("top", DEFAULT_MARGIN_TOP)),
            right=float(mapping.get("right", DEFAULT_MARGIN_RIGHT)),
            bottom=float(mapping.get("bottom", DEFAULT_MARGIN_BOTTOM)),
            left=float(mapping.get("left", DEFAULT_MARGIN_LEFT)),
        )

    def to_dict(self) -> dict[str, float]:
        return asdict(self)

    def clone(self) -> Margin:
        """Return a deep clone of this margin."""
        return Margin(
            top=self.top,
            right=self.right,
            bottom=self.bottom,
            left=self.left,
        )


@dataclass
class Position:
    """Top-left object position in the object's page unit."""

    x: float = 0.0
    y: float = 0.0

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> Position:
        if data is None:
            return cls()

        mapping = ensure_mapping(data, context="Report position")
        return cls(
            x=float(mapping.get("x", 0.0)),
            y=float(mapping.get("y", 0.0)),
        )

    @classmethod
    def from_value(
        cls,
        value: Position | Mapping[str, Any] | None,
        *,
        x: float = 0.0,
        y: float = 0.0,
    ) -> Position:
        """Return a Position from a Position, mapping, or fallback coordinates."""
        if value is None:
            return cls(x=x, y=y)
        if isinstance(value, Position):
            return value
        if isinstance(value, Mapping):
            return cls.from_dict(value)
        raise ReportValidationError("position must be a Position or mapping.")

    def to_dict(self) -> dict[str, float]:
        return asdict(self)

    def clone(self) -> Position:
        """Return a clone of this position."""
        return Position(x=self.x, y=self.y)


@dataclass
class Size:
    """Object dimensions in the object's page unit."""

    width: float = 0.0
    height: float = 0.0

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> Size:
        if data is None:
            return cls()

        mapping = ensure_mapping(data, context="Report size")
        return cls(
            width=float(mapping.get("width", 0.0)),
            height=float(mapping.get("height", 0.0)),
        )

    @classmethod
    def from_value(
        cls,
        value: Size | Mapping[str, Any] | None,
        *,
        width: float = 0.0,
        height: float = 0.0,
    ) -> Size:
        """Return a Size from a Size, mapping, or fallback dimensions."""
        if value is None:
            return cls(width=width, height=height)
        if isinstance(value, Size):
            return value
        if isinstance(value, Mapping):
            return cls.from_dict(value)
        raise ReportValidationError("size must be a Size or mapping.")

    def to_dict(self) -> dict[str, float]:
        return asdict(self)

    def clone(self) -> Size:
        """Return a clone of this size."""
        return Size(width=self.width, height=self.height)


@dataclass
class Page:
    """Report page settings."""

    width: float = DEFAULT_PAGE_WIDTH
    height: float = DEFAULT_PAGE_HEIGHT
    unit: str = DEFAULT_PAGE_UNIT
    orientation: str = DEFAULT_PAGE_ORIENTATION
    margin: Margin = field(default_factory=Margin)
    background_color: str = "#ffffff"
    transparent: bool = False
    id: str | None = None
    size: str | None = None
    _report: Any = field(default=None, init=False, repr=False, compare=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> Page:
        if data is None:
            return cls()

        mapping = ensure_mapping(data, context="Report page")
        size = _optional_str(mapping.get("size"))
        unit = str(mapping.get("unit", "px" if size else DEFAULT_PAGE_UNIT))
        default_width = DEFAULT_PAGE_WIDTH
        default_height = DEFAULT_PAGE_HEIGHT
        if size and "width" not in mapping and "height" not in mapping:
            default_width, default_height = _page_size_dimensions(size, unit)

        margin = _page_margin(mapping)
        return cls(
            width=float(mapping.get("width", default_width)),
            height=float(mapping.get("height", default_height)),
            unit=unit,
            orientation=str(mapping.get("orientation", DEFAULT_PAGE_ORIENTATION)),
            margin=margin,
            background_color=str(mapping.get("background_color", "#ffffff")),
            transparent=bool(mapping.get("transparent", False)),
            id=_optional_str(mapping.get("id")),
            size=size,
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "width": self.width,
            "height": self.height,
            "unit": self.unit,
            "orientation": self.orientation,
            "margin_top": self.margin.top,
            "margin_right": self.margin.right,
            "margin_bottom": self.margin.bottom,
            "margin_left": self.margin.left,
            "background_color": self.background_color,
            "transparent": self.transparent,
        }
        if self.id:
            data["id"] = self.id
        if self.size:
            data["size"] = self.size
        return data

    def clone(self, *, new_ids: bool = True) -> Page:
        """Return a deep clone of this page.

        By default, the clone receives a new page id. Pass ``new_ids=False``
        to preserve the current id.
        """
        return Page(
            width=self.width,
            height=self.height,
            unit=self.unit,
            orientation=self.orientation,
            margin=self.margin.clone(),
            background_color=self.background_color,
            transparent=self.transparent,
            id=_clone_id("page", self.id, new_ids=new_ids),
            size=self.size,
        )

    def validate(self) -> ReportValidationResult:
        """Validate this page and its page-owned objects."""
        from types import SimpleNamespace

        from .validation import validate_report

        report = self._report
        validation_target = SimpleNamespace(
            pages=[self],
            objects=list(self.objects) if report is not None else [],
            bands=getattr(report, "bands", []),
            layers=getattr(report, "layers", []),
            styles=getattr(report, "styles", {}),
            assets=getattr(report, "assets", []),
        )
        return validate_report(validation_target)

    def __call__(self) -> Page:
        """Return this page for fluent ``report.page()`` usage."""
        return self

    def __iter__(self) -> Iterator[Object]:
        """Iterate over objects that belong to this page."""
        return iter(self.objects)

    def __len__(self) -> int:
        """Return the number of objects on this page."""
        return len(self.objects)

    def __contains__(self, item: object) -> bool:
        """Return True when an object or object id belongs to this page."""
        if isinstance(item, Object):
            return item in self.objects
        if isinstance(item, str):
            return self.find(item) is not None
        return False

    def __getitem__(self, index: int) -> Object:
        """Return a page object by zero-based index."""
        return self.objects[index]

    def attach(self, report: Any) -> Page:
        """Attach this page to its owning report."""
        self._report = report
        return self

    @property
    def objects(self) -> list[Object]:
        """Return report objects that belong to this page."""
        report = self._require_report()
        page_id = self._ensure_id()
        first_page = report.pages[0] if getattr(report, "pages", []) else None
        return [
            report_object
            for report_object in report.objects
            if report_object.properties.get("page_id") == page_id
            or (report_object.properties.get("page_id") is None and self is first_page)
        ]

    def text(
        self,
        text: str,
        *,
        x: float = 0.0,
        y: float = 0.0,
        width: float = 300.0,
        height: float = 24.0,
        position: Position | Mapping[str, Any] | None = None,
        size: Size | Mapping[str, Any] | None = None,
        id: str | None = None,
        style: Style | Mapping[str, Any] | None = None,
        name: str | None = None,
        **style_values: Any,
    ) -> Object:
        """Add a text object to this page."""
        return self.add(
            _object_factory().create_text(
                text,
                id=id or "",
                x=x,
                y=y,
                width=width,
                height=height,
                position=position,
                size=size,
                style=style,
                style_values=style_values,
                properties=self._object_properties(name),
            )
        )

    def add(self, report_object: Object) -> Object:
        """Add an existing report object to this page."""
        if not isinstance(report_object, Object):
            raise ReportValidationError("page.add() expects a ReportObject.")
        report_object.properties["page_id"] = self._ensure_id()
        if not report_object.id:
            report_object.id = self._next_object_id(report_object.type)
        return self._add_object(report_object)

    def find(self, object_id: str) -> Object | None:
        """Return a page object by id, or None when it is not on this page."""
        return next(
            (report_object for report_object in self.objects if report_object.id == object_id),
            None,
        )

    def remove(self, object_id: str) -> Object:
        """Remove and return a page object by id."""
        report_object = self.find(object_id)
        if report_object is None:
            raise ReportObjectNotFoundError(f"Page object not found: {object_id}.")
        return self._require_report().remove_object(report_object.id)

    def clear(self) -> None:
        """Remove all objects from this page."""
        report = self._require_report()
        for report_object in list(self.objects):
            report.remove_object(report_object.id)

    def _object_properties(
        self,
        name: str | None = None,
        properties: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        resolved = dict(properties or {})
        if name is not None:
            resolved["name"] = name
        return resolved

    def _extract_style_values(self, properties: dict[str, Any]) -> dict[str, Any]:
        return {
            key: properties.pop(key)
            for key in tuple(properties)
            if key in _STYLE_KEYS
        }

    def field(
        self,
        binding: str,
        *,
        x: float = 0.0,
        y: float = 0.0,
        width: float = 300.0,
        height: float = 20.0,
        position: Position | Mapping[str, Any] | None = None,
        size: Size | Mapping[str, Any] | None = None,
        id: str | None = None,
        style: Style | Mapping[str, Any] | None = None,
        name: str | None = None,
        **style_values: Any,
    ) -> Object:
        """Add a field object to this page."""
        return self.add(
            _object_factory().create_field(
                binding,
                id=id or "",
                x=x,
                y=y,
                width=width,
                height=height,
                position=position,
                size=size,
                style=style,
                style_values=style_values,
                properties=self._object_properties(name),
            )
        )

    def line(
        self,
        *,
        x: float = 0.0,
        y: float = 0.0,
        width: float = 300.0,
        height: float = 0.0,
        position: Position | Mapping[str, Any] | None = None,
        size: Size | Mapping[str, Any] | None = None,
        id: str | None = None,
        style: Style | Mapping[str, Any] | None = None,
        name: str | None = None,
        **style_values: Any,
    ) -> Object:
        """Add a line object to this page."""
        return self.add(
            _object_factory().create_line(
                id=id or "",
                x=x,
                y=y,
                width=width,
                height=height,
                position=position,
                size=size,
                style=style,
                style_values=style_values,
                properties=self._object_properties(name),
            )
        )

    def rectangle(
        self,
        *,
        x: float = 0.0,
        y: float = 0.0,
        width: float = 300.0,
        height: float = 100.0,
        position: Position | Mapping[str, Any] | None = None,
        size: Size | Mapping[str, Any] | None = None,
        id: str | None = None,
        style: Style | Mapping[str, Any] | None = None,
        name: str | None = None,
        **style_values: Any,
    ) -> Object:
        """Add a rectangle object to this page."""
        return self.add(
            _object_factory().create_rectangle(
                id=id or "",
                x=x,
                y=y,
                width=width,
                height=height,
                position=position,
                size=size,
                style=style,
                style_values=style_values,
                properties=self._object_properties(name),
            )
        )

    def image(
        self,
        source: str,
        *,
        x: float = 0.0,
        y: float = 0.0,
        width: float = 100.0,
        height: float = 100.0,
        position: Position | Mapping[str, Any] | None = None,
        size: Size | Mapping[str, Any] | None = None,
        id: str | None = None,
        style: Style | Mapping[str, Any] | None = None,
        name: str | None = None,
        **properties: Any,
    ) -> Object:
        """Add an image placeholder object to this page."""
        style_values = self._extract_style_values(properties)
        return self.add(
            _object_factory().create_image(
                source,
                id=id or "",
                x=x,
                y=y,
                width=width,
                height=height,
                position=position,
                size=size,
                style=style,
                style_values=style_values,
                properties=self._object_properties(name, properties),
            )
        )

    def barcode(
        self,
        value: str,
        *,
        x: float = 0.0,
        y: float = 0.0,
        width: float = 200.0,
        height: float = 60.0,
        position: Position | Mapping[str, Any] | None = None,
        size: Size | Mapping[str, Any] | None = None,
        id: str | None = None,
        symbology: str = "code128",
        style: Style | Mapping[str, Any] | None = None,
        name: str | None = None,
        **properties: Any,
    ) -> Object:
        """Add a barcode placeholder object to this page."""
        style_values = self._extract_style_values(properties)
        return self.add(
            _object_factory().create_barcode(
                value,
                id=id or "",
                x=x,
                y=y,
                width=width,
                height=height,
                position=position,
                size=size,
                symbology=symbology,
                style=style,
                style_values=style_values,
                properties=self._object_properties(name, properties),
            )
        )

    def qrcode(
        self,
        value: str,
        *,
        x: float = 0.0,
        y: float = 0.0,
        width: float = 100.0,
        height: float = 100.0,
        position: Position | Mapping[str, Any] | None = None,
        size: Size | Mapping[str, Any] | None = None,
        id: str | None = None,
        style: Style | Mapping[str, Any] | None = None,
        name: str | None = None,
        **properties: Any,
    ) -> Object:
        """Add a QR code placeholder object to this page."""
        style_values = self._extract_style_values(properties)
        return self.add(
            _object_factory().create_qrcode(
                value,
                id=id or "",
                x=x,
                y=y,
                width=width,
                height=height,
                position=position,
                size=size,
                style=style,
                style_values=style_values,
                properties=self._object_properties(name, properties),
            )
        )

    def table(
        self,
        *,
        x: float = 0.0,
        y: float = 0.0,
        width: float = 300.0,
        height: float = 100.0,
        binding: str | None = None,
        columns: list[Mapping[str, Any]] | None = None,
        position: Position | Mapping[str, Any] | None = None,
        size: Size | Mapping[str, Any] | None = None,
        id: str | None = None,
        style: Style | Mapping[str, Any] | None = None,
        name: str | None = None,
        **properties: Any,
    ) -> Object:
        """Add a table placeholder object to this page."""
        style_values = self._extract_style_values(properties)
        return self.add(
            _object_factory().create_table(
                id=id or "",
                x=x,
                y=y,
                width=width,
                height=height,
                binding=binding,
                columns=columns,
                position=position,
                size=size,
                style=style,
                style_values=style_values,
                properties=self._object_properties(name, properties),
            )
        )

    def object(
        self,
        object_type: str,
        *,
        x: float = 0.0,
        y: float = 0.0,
        width: float = 0.0,
        height: float = 0.0,
        position: Position | Mapping[str, Any] | None = None,
        size: Size | Mapping[str, Any] | None = None,
        id: str | None = None,
        style: Style | Mapping[str, Any] | None = None,
        name: str | None = None,
        **properties: Any,
    ) -> Object:
        """Add a custom object type to this page."""
        style_values = self._extract_style_values(properties)
        return self.add(
            _object_factory().create_custom(
                object_type,
                id=id or "",
                x=x,
                y=y,
                width=width,
                height=height,
                position=position,
                size=size,
                style=style,
                style_values=style_values,
                properties=self._object_properties(name, properties),
            )
        )

    def _add_object(self, report_object: Object) -> Object:
        return self._require_report().add_object(report_object)

    def _require_report(self) -> Any:
        if self._report is None:
            raise ReportValidationError("Page must belong to a Report before adding objects.")
        return self._report

    def _ensure_id(self) -> str:
        if self.id is None:
            report = self._require_report()
            self.id = _next_available_id(
                "page",
                {page.id for page in report.pages if page.id is not None},
            )
        return self.id

    def _next_object_id(self, object_type: str) -> str:
        report = self._require_report()
        existing_ids = {report_object.id for report_object in report.objects}
        return _next_available_id(_safe_id_prefix(object_type), existing_ids)


@dataclass(init=False)
class Style:
    """Named or inline object style with optional inheritance."""

    values: dict[str, Any]
    parent: Style | None
    name: str | None

    def __init__(
        self,
        values: Mapping[str, Any] | None = None,
        *,
        parent: Style | Mapping[str, Any] | None = None,
        name: str | None = None,
        **style_values: Any,
    ) -> None:
        self.values = dict(values or {})
        self.values.update(style_values)
        self.parent = _style_parent(parent)
        self.name = name

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> Style:
        if data is None:
            return cls()
        mapping = dict(ensure_mapping(data, context="Report style"))
        parent = mapping.pop("parent", mapping.pop("inherits", None))
        name = _optional_str(mapping.pop("name", None))
        return cls(mapping, parent=_style_parent(parent), name=name)

    def get(self, key: str, default: Any = None) -> Any:
        """Return a style value."""
        return self.resolved_values().get(key, default)

    def inherit(self, **style_values: Any) -> Style:
        """Return a child style that inherits this style."""
        return Style(parent=self, **style_values)

    def resolved_values(self) -> dict[str, Any]:
        """Return style values after applying inherited parent values."""
        resolved = self.parent.resolved_values() if self.parent is not None else {}
        resolved.update(self.values)
        return resolved

    def to_dict(self) -> dict[str, Any]:
        return self.resolved_values()

    def clone(self) -> Style:
        """Return a deep clone of this style."""
        return Style(
            copy.deepcopy(self.values),
            parent=self.parent.clone() if self.parent is not None else None,
            name=self.name,
        )


@dataclass
class Binding:
    """Data binding expression for a report object."""

    expression: str = ""

    @classmethod
    def from_value(cls, value: Any) -> Binding | None:
        if value is None:
            return None
        if isinstance(value, Binding):
            return value
        if isinstance(value, Mapping):
            expression = value.get("expression", "")
        else:
            expression = value
        expression_str = str(expression)
        if not expression_str:
            return None
        return cls(expression=expression_str)

    def to_dict(self) -> str:
        return self.expression

    def clone(self) -> Binding:
        """Return a clone of this binding."""
        return Binding(expression=self.expression)


@dataclass(init=False)
class Object:
    """Positioned report object."""

    id: str
    type: str
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    text: str = ""
    binding: Binding | None = None
    style: Style = field(default_factory=Style)
    band_id: str | None = None
    layer_id: str | None = None
    z_index: int = 0
    visible: bool = True
    properties: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        type: str,
        x: float = 0.0,
        y: float = 0.0,
        width: float = 0.0,
        height: float = 0.0,
        *,
        position: Position | Mapping[str, Any] | None = None,
        size: Size | Mapping[str, Any] | None = None,
        text: str = "",
        binding: Binding | Mapping[str, Any] | str | None = None,
        style: Style | Mapping[str, Any] | None = None,
        band_id: str | None = None,
        layer_id: str | None = None,
        z_index: int = 0,
        visible: bool = True,
        properties: Mapping[str, Any] | None = None,
    ) -> None:
        resolved_position = Position.from_value(position, x=x, y=y)
        resolved_size = Size.from_value(size, width=width, height=height)

        self.id = id
        self.type = type
        self.x = resolved_position.x
        self.y = resolved_position.y
        self.width = resolved_size.width
        self.height = resolved_size.height
        self.text = text
        self.binding = Binding.from_value(binding)
        self.style = _style_value(style)
        self.band_id = band_id
        self.layer_id = layer_id
        self.z_index = z_index
        self.visible = visible
        self.properties = dict(properties or {})
        self.__post_init__()

    def __post_init__(self) -> None:
        if not self.text and "text" in self.properties:
            self.text = str(self.properties["text"])
        if self.binding is None:
            self.binding = Binding.from_value(
                self.properties.get(
                    "binding",
                    self.properties.get("field", self.properties.get("expression")),
                )
            )
        if not self.style.resolved_values() and isinstance(self.properties.get("style"), Mapping):
            self.style = Style.from_dict(self.properties["style"])
        if self.band_id is None:
            self.band_id = _optional_str(self.properties.get("band", self.properties.get("band_id")))

    @property
    def position(self) -> Position:
        """Return this object's position."""
        return Position(x=self.x, y=self.y)

    @position.setter
    def position(self, value: Position | Mapping[str, Any]) -> None:
        resolved = Position.from_value(value)
        self.x = resolved.x
        self.y = resolved.y

    @property
    def size(self) -> Size:
        """Return this object's size."""
        return Size(width=self.width, height=self.height)

    @size.setter
    def size(self, value: Size | Mapping[str, Any]) -> None:
        resolved = Size.from_value(value)
        self.width = resolved.width
        self.height = resolved.height

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Object:
        return _object_factory().create_from_dict(
            data,
            object_class=None if cls is Object else cls,
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "type": self.type,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "z_index": self.z_index,
            "visible": self.visible,
            "properties": dict(self.properties),
        }
        if self.text:
            data["text"] = self.text
            data["properties"]["text"] = self.text
        if self.binding is not None:
            data["binding"] = self.binding.expression
            data["properties"]["binding"] = self.binding.expression
        if self.style.resolved_values():
            data["style"] = self.style.to_dict()
            data["properties"]["style"] = self.style.to_dict()
        if self.band_id is not None:
            data["band"] = self.band_id
            data["band_id"] = self.band_id
        if self.layer_id is not None:
            data["layer_id"] = self.layer_id
        return data

    def clone(self, *, new_ids: bool = True) -> Object:
        """Return a deep clone of this report object.

        By default, the clone receives a new object id. Pass ``new_ids=False``
        to preserve the current id.
        """
        data = self.to_dict()
        data["id"] = _clone_id("object", self.id, new_ids=new_ids)
        cloned = Object.from_dict(data)
        cloned.position = self.position.clone()
        cloned.size = self.size.clone()
        cloned.text = self.text
        cloned.binding = self.binding.clone() if self.binding is not None else None
        cloned.style = self.style.clone()
        cloned.band_id = self.band_id
        cloned.layer_id = self.layer_id
        cloned.z_index = self.z_index
        cloned.visible = self.visible
        cloned.properties = copy.deepcopy(self.properties)
        return cloned


class TextObject(Object):
    """Text drawable report object."""

    def __init__(
        self,
        text: str,
        *,
        id: str = "",
        x: float = 0.0,
        y: float = 0.0,
        width: float = 300.0,
        height: float = 24.0,
        position: Position | Mapping[str, Any] | None = None,
        size: Size | Mapping[str, Any] | None = None,
        style: Style | Mapping[str, Any] | None = None,
        band_id: str | None = None,
        layer_id: str | None = None,
        z_index: int = 0,
        visible: bool = True,
        properties: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            id=id,
            type="text",
            x=x,
            y=y,
            width=width,
            height=height,
            position=position,
            size=size,
            text=text,
            style=style,
            band_id=band_id,
            layer_id=layer_id,
            z_index=z_index,
            visible=visible,
            properties=properties,
        )
        self.properties["text"] = text


class FieldObject(Object):
    """Data-bound field drawable report object."""

    def __init__(
        self,
        binding: str,
        *,
        id: str = "",
        x: float = 0.0,
        y: float = 0.0,
        width: float = 300.0,
        height: float = 20.0,
        position: Position | Mapping[str, Any] | None = None,
        size: Size | Mapping[str, Any] | None = None,
        style: Style | Mapping[str, Any] | None = None,
        band_id: str | None = None,
        layer_id: str | None = None,
        z_index: int = 0,
        visible: bool = True,
        properties: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            id=id,
            type="field",
            x=x,
            y=y,
            width=width,
            height=height,
            position=position,
            size=size,
            binding=binding,
            style=style,
            band_id=band_id,
            layer_id=layer_id,
            z_index=z_index,
            visible=visible,
            properties=properties,
        )
        self.properties["binding"] = binding


class LineObject(Object):
    """Line drawable report object."""

    def __init__(
        self,
        *,
        id: str = "",
        x: float = 0.0,
        y: float = 0.0,
        width: float = 300.0,
        height: float = 0.0,
        position: Position | Mapping[str, Any] | None = None,
        size: Size | Mapping[str, Any] | None = None,
        style: Style | Mapping[str, Any] | None = None,
        band_id: str | None = None,
        layer_id: str | None = None,
        z_index: int = 0,
        visible: bool = True,
        properties: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            id=id,
            type="line",
            x=x,
            y=y,
            width=width,
            height=height,
            position=position,
            size=size,
            style=style,
            band_id=band_id,
            layer_id=layer_id,
            z_index=z_index,
            visible=visible,
            properties=properties,
        )


class RectangleObject(Object):
    """Rectangle drawable report object."""

    def __init__(
        self,
        *,
        id: str = "",
        x: float = 0.0,
        y: float = 0.0,
        width: float = 300.0,
        height: float = 100.0,
        position: Position | Mapping[str, Any] | None = None,
        size: Size | Mapping[str, Any] | None = None,
        style: Style | Mapping[str, Any] | None = None,
        band_id: str | None = None,
        layer_id: str | None = None,
        z_index: int = 0,
        visible: bool = True,
        properties: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            id=id,
            type="rectangle",
            x=x,
            y=y,
            width=width,
            height=height,
            position=position,
            size=size,
            style=style,
            band_id=band_id,
            layer_id=layer_id,
            z_index=z_index,
            visible=visible,
            properties=properties,
        )


class ImageObject(Object):
    """Image placeholder report object."""

    def __init__(
        self,
        source: str,
        *,
        id: str = "",
        x: float = 0.0,
        y: float = 0.0,
        width: float = 100.0,
        height: float = 100.0,
        position: Position | Mapping[str, Any] | None = None,
        size: Size | Mapping[str, Any] | None = None,
        style: Style | Mapping[str, Any] | None = None,
        band_id: str | None = None,
        layer_id: str | None = None,
        z_index: int = 0,
        visible: bool = True,
        properties: Mapping[str, Any] | None = None,
    ) -> None:
        merged_properties = dict(properties or {})
        merged_properties["source"] = source
        super().__init__(
            id=id,
            type="image",
            x=x,
            y=y,
            width=width,
            height=height,
            position=position,
            size=size,
            style=style,
            band_id=band_id,
            layer_id=layer_id,
            z_index=z_index,
            visible=visible,
            properties=merged_properties,
        )


class BarcodeObject(Object):
    """Barcode placeholder report object."""

    def __init__(
        self,
        value: str,
        *,
        id: str = "",
        x: float = 0.0,
        y: float = 0.0,
        width: float = 200.0,
        height: float = 60.0,
        position: Position | Mapping[str, Any] | None = None,
        size: Size | Mapping[str, Any] | None = None,
        symbology: str = "code128",
        style: Style | Mapping[str, Any] | None = None,
        band_id: str | None = None,
        layer_id: str | None = None,
        z_index: int = 0,
        visible: bool = True,
        properties: Mapping[str, Any] | None = None,
    ) -> None:
        merged_properties = dict(properties or {})
        merged_properties["value"] = value
        merged_properties["symbology"] = symbology
        super().__init__(
            id=id,
            type="barcode",
            x=x,
            y=y,
            width=width,
            height=height,
            position=position,
            size=size,
            style=style,
            band_id=band_id,
            layer_id=layer_id,
            z_index=z_index,
            visible=visible,
            properties=merged_properties,
        )


class QRCodeObject(Object):
    """QR code placeholder report object."""

    def __init__(
        self,
        value: str,
        *,
        id: str = "",
        x: float = 0.0,
        y: float = 0.0,
        width: float = 100.0,
        height: float = 100.0,
        position: Position | Mapping[str, Any] | None = None,
        size: Size | Mapping[str, Any] | None = None,
        style: Style | Mapping[str, Any] | None = None,
        band_id: str | None = None,
        layer_id: str | None = None,
        z_index: int = 0,
        visible: bool = True,
        properties: Mapping[str, Any] | None = None,
    ) -> None:
        merged_properties = dict(properties or {})
        merged_properties["value"] = value
        super().__init__(
            id=id,
            type="qrcode",
            x=x,
            y=y,
            width=width,
            height=height,
            position=position,
            size=size,
            style=style,
            band_id=band_id,
            layer_id=layer_id,
            z_index=z_index,
            visible=visible,
            properties=merged_properties,
        )


class TableObject(Object):
    """Table placeholder report object."""

    def __init__(
        self,
        *,
        id: str = "",
        x: float = 0.0,
        y: float = 0.0,
        width: float = 300.0,
        height: float = 100.0,
        binding: str | None = None,
        columns: list[Mapping[str, Any]] | None = None,
        position: Position | Mapping[str, Any] | None = None,
        size: Size | Mapping[str, Any] | None = None,
        style: Style | Mapping[str, Any] | None = None,
        band_id: str | None = None,
        layer_id: str | None = None,
        z_index: int = 0,
        visible: bool = True,
        properties: Mapping[str, Any] | None = None,
    ) -> None:
        merged_properties = dict(properties or {})
        if binding is not None:
            merged_properties["binding"] = binding
        if columns is not None:
            merged_properties["columns"] = [dict(column) for column in columns]
        super().__init__(
            id=id,
            type="table",
            x=x,
            y=y,
            width=width,
            height=height,
            position=position,
            size=size,
            style=style,
            band_id=band_id,
            layer_id=layer_id,
            z_index=z_index,
            visible=visible,
            properties=merged_properties,
        )


@dataclass
class Band:
    """Layout band for grouping report objects."""

    id: str
    type: str
    name: str | None = None
    y: float = 0.0
    height: float = 0.0
    background_color: str = "transparent"
    visible: bool = True
    locked: bool = False
    properties: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Band:
        mapping = ensure_mapping(data, context="Report band")
        raw_properties = mapping.get("properties", {})
        properties = ensure_mapping(raw_properties or {}, context="Report band properties")
        return cls(
            id=_required_str(mapping, "id", context="Report band"),
            type=_required_str(mapping, "type", context="Report band"),
            name=_optional_str(mapping.get("name")),
            y=float(mapping.get("y", mapping.get("top", 0.0))),
            height=float(mapping.get("height", 0.0)),
            background_color=str(mapping.get("background_color", properties.get("background_color", "transparent"))),
            visible=bool(mapping.get("visible", True)),
            locked=bool(mapping.get("locked", False)),
            properties=dict(properties),
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.name is None:
            data.pop("name", None)
        return data

    def clone(self, *, new_ids: bool = True) -> Band:
        """Return a deep clone of this band."""
        return Band(
            id=_clone_id("band", self.id, new_ids=new_ids),
            type=self.type,
            name=self.name,
            y=self.y,
            height=self.height,
            background_color=self.background_color,
            visible=self.visible,
            locked=self.locked,
            properties=copy.deepcopy(self.properties),
        )


@dataclass
class Layer:
    """Optional visual layer for grouping report objects."""

    id: str
    name: str
    visible: bool = True
    z_index: int = 0
    properties: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Layer:
        mapping = ensure_mapping(data, context="Report layer")
        layer_id = _required_str(mapping, "id", context="Report layer")
        return cls(
            id=layer_id,
            name=str(mapping.get("name", layer_id)),
            visible=bool(mapping.get("visible", True)),
            z_index=int(mapping.get("z_index", 0)),
            properties=dict(mapping.get("properties", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def clone(self, *, new_ids: bool = True) -> Layer:
        """Return a deep clone of this layer."""
        return Layer(
            id=_clone_id("layer", self.id, new_ids=new_ids),
            name=self.name,
            visible=self.visible,
            z_index=self.z_index,
            properties=copy.deepcopy(self.properties),
        )


@dataclass
class Asset:
    """External or embedded report asset."""

    id: str
    type: str
    source: str
    name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Asset:
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

    def clone(self, *, new_ids: bool = True) -> Asset:
        """Return a deep clone of this asset."""
        return Asset(
            id=_clone_id("asset", self.id, new_ids=new_ids),
            type=self.type,
            source=self.source,
            name=self.name,
            metadata=copy.deepcopy(self.metadata),
        )


@dataclass
class ReportTemplate:
    """Legacy JSON template adapter.

    New code should use :class:`slim_report_core.Report` as the domain model.
    This adapter remains for JSON compatibility and existing callers.
    """

    version: str = DEFAULT_REPORT_VERSION
    metadata: Metadata = field(default_factory=Metadata)
    page: Page = field(default_factory=Page)
    objects: list[Object] = field(default_factory=list)
    bands: list[Band] = field(default_factory=list)
    assets: list[Asset] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ReportTemplate:
        mapping = ensure_mapping(data, context="Report template")
        validate_template_mapping(mapping)
        return cls(
            version=str(mapping["version"]),
            metadata=Metadata.from_dict(mapping["metadata"]),
            page=Page.from_dict(mapping["page"]),
            objects=[Object.from_dict(item) for item in mapping["objects"]],
            bands=[Band.from_dict(item) for item in mapping["bands"]],
            assets=[Asset.from_dict(item) for item in mapping["assets"]],
            data=copy.deepcopy(mapping.get("data", {})) if isinstance(mapping.get("data"), Mapping) else {},
        )

    def to_dict(self) -> dict[str, Any]:
        data = {
            "version": self.version,
            "metadata": self.metadata.to_dict(),
            "page": self.page.to_dict(),
            "objects": [item.to_dict() for item in self.objects],
            "bands": [item.to_dict() for item in self.bands],
            "assets": [item.to_dict() for item in self.assets],
        }
        if self.data:
            data["data"] = copy.deepcopy(self.data)
        return data


def clone_model(value: Any) -> Any:
    """Return a deep copy of a domain model value."""
    return copy.deepcopy(value)


def _clone_id(prefix: str, value: str | None, *, new_ids: bool) -> str | None:
    if not new_ids:
        return value
    return f"{prefix}_{uuid.uuid4().hex}"


ReportMetadata = Metadata
ReportPage = Page
ReportObject = Object
ReportBand = Band
ReportAsset = Asset


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _required_str(mapping: Mapping[str, Any], key: str, *, context: str) -> str:
    value = mapping.get(key)
    if value is None or str(value).strip() == "":
        raise ReportValidationError(f"{context} requires a non-empty {key}.")
    return str(value)


def _page_margin(mapping: Mapping[str, Any]) -> Margin:
    margin = mapping.get("margin")
    if isinstance(margin, Mapping):
        return Margin.from_dict(margin)
    return Margin(
        top=float(mapping.get("margin_top", DEFAULT_MARGIN_TOP)),
        right=float(mapping.get("margin_right", DEFAULT_MARGIN_RIGHT)),
        bottom=float(mapping.get("margin_bottom", DEFAULT_MARGIN_BOTTOM)),
        left=float(mapping.get("margin_left", DEFAULT_MARGIN_LEFT)),
    )


def _style_parent(value: Any) -> Style | None:
    if value is None or isinstance(value, str):
        return None
    if isinstance(value, Style):
        return value
    if isinstance(value, Mapping):
        return Style.from_dict(value)
    raise ReportValidationError("Style parent must be a Style or mapping.")


def _style_value(value: Any) -> Style:
    if value is None:
        return Style()
    if isinstance(value, Style):
        return value
    if isinstance(value, Mapping):
        return Style.from_dict(value)
    raise ReportValidationError("style must be a Style or mapping.")


def _object_factory() -> Any:
    from .object_factory import ObjectFactory

    return ObjectFactory()


def _next_available_id(prefix: str, existing_ids: set[str]) -> str:
    index = 1
    while True:
        candidate = f"{prefix}_{index}"
        if candidate not in existing_ids:
            return candidate
        index += 1


def _safe_id_prefix(value: str) -> str:
    prefix = "".join(char if char.isalnum() else "_" for char in value.lower()).strip("_")
    return prefix or "object"


def _page_size_dimensions(size: str, unit: str) -> tuple[float, float]:
    normalized_size = size.lower()
    normalized_unit = unit.lower()
    sizes_in_px = {
        "letter": (612.0, 792.0),
        "legal": (612.0, 1008.0),
        "a4": (595.0, 842.0),
        "custom": (595.0, 842.0),
    }
    sizes_in_inches = {
        "letter": (8.5, 11.0),
        "legal": (8.5, 14.0),
        "a4": (210.0 / 25.4, 297.0 / 25.4),
        "custom": (8.5, 11.0),
    }
    if normalized_size not in sizes_in_inches:
        raise ReportValidationError(f"Unsupported page size: {size}.")

    if normalized_unit == "px":
        return sizes_in_px[normalized_size]

    width_in, height_in = sizes_in_inches[normalized_size]
    if normalized_unit == "in":
        return width_in, height_in
    if normalized_unit == "pt":
        return width_in * 72.0, height_in * 72.0
    if normalized_unit == "mm":
        return width_in * 25.4, height_in * 25.4
    if normalized_unit == "cm":
        return width_in * 2.54, height_in * 2.54

    raise ReportValidationError(f"Unsupported page unit: {unit}.")
