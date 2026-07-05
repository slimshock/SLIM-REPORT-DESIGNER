"""Builder API for creating Report domain objects."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..models import Binding, Margin, Object, Page, Position, Size, Style
from ..report import Report

PositionInput = Position | Mapping[str, Any] | None
SizeInput = Size | Mapping[str, Any] | None
StyleInput = Style | Mapping[str, Any] | None


class StyleBuilder:
    """Fluent builder for inline or named styles."""

    def __init__(self, initial: StyleInput = None) -> None:
        self._style = _style_from(initial)

    def set(self, key: str, value: Any) -> StyleBuilder:
        """Set a style value."""
        self._style.values[key] = value
        return self

    def update(self, **values: Any) -> StyleBuilder:
        """Set multiple style values."""
        self._style.values.update(values)
        return self

    def font_size(self, value: float) -> StyleBuilder:
        """Set the font size."""
        return self.set("font_size", value)

    def font_family(self, value: str) -> StyleBuilder:
        """Set the font family."""
        return self.set("font_family", value)

    def bold(self, value: bool = True) -> StyleBuilder:
        """Set bold text rendering."""
        return self.set("bold", value)

    def italic(self, value: bool = True) -> StyleBuilder:
        """Set italic text rendering."""
        return self.set("italic", value)

    def color(self, value: str) -> StyleBuilder:
        """Set the foreground color."""
        return self.set("color", value)

    def fill_color(self, value: str) -> StyleBuilder:
        """Set the fill color."""
        return self.set("fill_color", value)

    def border_width(self, value: float) -> StyleBuilder:
        """Set the rectangle border width."""
        return self.set("border_width", value)

    def stroke_width(self, value: float) -> StyleBuilder:
        """Set the line stroke width."""
        return self.set("stroke_width", value)

    def align(self, value: str) -> StyleBuilder:
        """Set text alignment."""
        return self.set("align", value)

    def build(self) -> Style:
        """Return a new Style domain object."""
        return self._style.clone()


class PageBuilder:
    """Fluent builder for a Page domain object."""

    def __init__(self, page: Page | None = None, parent: ReportBuilder | None = None) -> None:
        self._page = page or Page()
        self._parent = parent

    def size(
        self,
        size: str,
        *,
        orientation: str | None = None,
        unit: str | None = None,
    ) -> PageBuilder:
        """Set a named page size such as A4 or Letter."""
        self._page.size = size.lower()
        self._page.unit = unit or "px"
        if orientation is not None:
            self._page.orientation = orientation.lower()
        return self

    def dimensions(
        self,
        width: float,
        height: float,
        *,
        unit: str | None = None,
    ) -> PageBuilder:
        """Set custom page dimensions."""
        self._page.width = width
        self._page.height = height
        self._page.size = None
        if unit is not None:
            self._page.unit = unit
        return self

    def portrait(self) -> PageBuilder:
        """Set portrait orientation."""
        self._page.orientation = "portrait"
        return self

    def landscape(self) -> PageBuilder:
        """Set landscape orientation."""
        self._page.orientation = "landscape"
        return self

    def margins(
        self,
        top: float,
        right: float | None = None,
        bottom: float | None = None,
        left: float | None = None,
    ) -> PageBuilder:
        """Set page margins.

        Passing one value applies it to every side. Passing two values applies
        vertical and horizontal margins.
        """
        resolved_right = top if right is None else right
        resolved_bottom = top if bottom is None else bottom
        resolved_left = resolved_right if left is None else left
        self._page.margin = Margin(
            top=top,
            right=resolved_right,
            bottom=resolved_bottom,
            left=resolved_left,
        )
        return self

    def margin(
        self,
        top: float,
        right: float | None = None,
        bottom: float | None = None,
        left: float | None = None,
    ) -> PageBuilder:
        """Set page margins."""
        return self.margins(top, right, bottom, left)

    def id(self, page_id: str) -> PageBuilder:
        """Set the page id."""
        self._page.id = page_id
        return self

    def done(self) -> ReportBuilder:
        """Return the parent ReportBuilder."""
        if self._parent is None:
            msg = "PageBuilder has no parent ReportBuilder."
            raise RuntimeError(msg)
        return self._parent

    def build(self) -> Page:
        """Return the Page domain object."""
        return self._page


class ObjectBuilder:
    """Fluent builder for a positioned Object domain object."""

    def __init__(
        self,
        object_type: str,
        *,
        object_id: str,
        parent: ReportBuilder | None = None,
        **properties: Any,
    ) -> None:
        self._parent = parent
        position = properties.pop("position", None)
        size = properties.pop("size", None)
        self._object = Object(
            id=object_id,
            type=object_type,
            x=float(properties.pop("x", 0.0)),
            y=float(properties.pop("y", 0.0)),
            width=float(properties.pop("width", 0.0)),
            height=float(properties.pop("height", 0.0)),
            position=position,
            size=size,
            properties=dict(properties),
        )

    def position(
        self,
        position: PositionInput = None,
        *,
        x: float | None = None,
        y: float | None = None,
        width: float | None = None,
        height: float | None = None,
    ) -> ObjectBuilder:
        """Set object position and optional dimensions."""
        current = self._object.position
        self._object.position = Position.from_value(
            position,
            x=current.x if x is None else x,
            y=current.y if y is None else y,
        )
        if width is not None:
            self._object.width = width
        if height is not None:
            self._object.height = height
        return self

    def size(
        self,
        size: SizeInput = None,
        *,
        width: float | None = None,
        height: float | None = None,
    ) -> ObjectBuilder:
        """Set object dimensions."""
        current = self._object.size
        self._object.size = Size.from_value(
            size,
            width=current.width if width is None else width,
            height=current.height if height is None else height,
        )
        return self

    def text(self, value: str) -> ObjectBuilder:
        """Set text content."""
        self._object.text = value
        self._object.properties["text"] = value
        return self

    def binding(self, expression: str) -> ObjectBuilder:
        """Set the data binding expression."""
        self._object.binding = Binding(expression=expression)
        self._object.properties["binding"] = expression
        return self

    def style(self, style: StyleInput = None, **values: Any) -> ObjectBuilder:
        """Set or update inline style values."""
        if style is not None:
            self._object.style = _style_from(style)
        if values:
            self._object.style.values.update(values)
        self._object.properties["style"] = self._object.style.to_dict()
        return self

    def name(self, value: str) -> ObjectBuilder:
        """Set a developer-facing object name."""
        self._object.properties["name"] = value
        return self

    def property(self, key: str, value: Any) -> ObjectBuilder:
        """Set a custom object property."""
        self._object.properties[key] = value
        return self

    def add(self) -> ReportBuilder:
        """Add the object to the parent report and return the ReportBuilder."""
        if self._parent is None:
            msg = "ObjectBuilder has no parent ReportBuilder."
            raise RuntimeError(msg)
        self._parent._add_built_object(self.build())
        return self._parent

    def build(self) -> Object:
        """Return the Object domain object."""
        return self._object


class ReportBuilder:
    """Fluent builder that creates a Report domain object."""

    def __init__(self, title: str | None = None) -> None:
        self._report = Report()
        self._id_counts: dict[str, int] = {}
        self._current_page = self._report.page
        self._ensure_page_id(self._current_page)
        self._current_page.size = "letter"
        self._current_page.unit = "px"
        if title:
            self._report.metadata.title = title

    @property
    def report(self) -> Report:
        """Return the report currently being built."""
        return self._report

    def metadata(
        self,
        *,
        title: str | None = None,
        subtitle: str | None = None,
        description: str | None = None,
        author: str | None = None,
        tags: list[str] | None = None,
        **custom: Any,
    ) -> ReportBuilder:
        """Set report metadata values."""
        if title is not None:
            self._report.metadata.title = title
        if subtitle is not None:
            self._report.metadata.custom["subtitle"] = subtitle
        if description is not None:
            self._report.metadata.description = description
        if author is not None:
            self._report.metadata.author = author
        if tags is not None:
            self._report.metadata.tags = list(tags)
        if custom:
            self._report.metadata.custom.update(custom)
        return self

    def page(
        self,
        size: str | None = None,
        *,
        width: float | None = None,
        height: float | None = None,
        unit: str | None = None,
        orientation: str = "portrait",
        id: str | None = None,
    ) -> ReportBuilder:
        """Configure the current report page and return this builder."""
        page = self._ensure_current_page()
        if id is not None:
            page.id = id
        page.orientation = orientation.lower()
        if size is not None:
            page.size = size.lower()
            page.unit = unit or "px"
        if width is not None:
            page.width = width
            page.size = None
        if height is not None:
            page.height = height
            page.size = None
        if unit is not None:
            page.unit = unit
        return self

    def margin(
        self,
        top: float,
        right: float | None = None,
        bottom: float | None = None,
        left: float | None = None,
    ) -> ReportBuilder:
        """Set margins on the current page."""
        self._ensure_current_page().margin = _margin_from(top, right, bottom, left)
        return self

    def landscape(self) -> ReportBuilder:
        """Set the current page orientation to landscape."""
        self._ensure_current_page().orientation = "landscape"
        return self

    def portrait(self) -> ReportBuilder:
        """Set the current page orientation to portrait."""
        self._ensure_current_page().orientation = "portrait"
        return self

    def page_break(self) -> ReportBuilder:
        """Start a new page and make it the current page."""
        current_page = self._ensure_current_page()
        return self.new_page(
            current_page.size,
            width=current_page.width,
            height=current_page.height,
            unit=current_page.unit,
            orientation=current_page.orientation,
        )

    def new_page(
        self,
        size: str | None = None,
        *,
        width: float | None = None,
        height: float | None = None,
        unit: str | None = None,
        orientation: str = "portrait",
        id: str | None = None,
    ) -> ReportBuilder:
        """Add a new page, make it current, and return this builder."""
        page = self._create_page(
            size=size,
            width=width,
            height=height,
            unit=unit,
            orientation=orientation,
            id=id,
        )
        self._report.add_page(page)
        self._current_page = page
        return self

    def page_builder(self) -> PageBuilder:
        """Return a builder for the current report page."""
        return PageBuilder(self._current_page, parent=self)

    def add_page(
        self,
        size: str | None = None,
        *,
        width: float | None = None,
        height: float | None = None,
        unit: str | None = None,
        orientation: str = "portrait",
        id: str | None = None,
    ) -> PageBuilder:
        """Add a page, make it current, and return a PageBuilder for it."""
        page = self._create_page(
            size=size,
            width=width,
            height=height,
            unit=unit,
            orientation=orientation,
            id=id,
        )
        self._report.add_page(page)
        self._current_page = page
        return PageBuilder(page, parent=self)

    def text(
        self,
        text: str,
        *,
        x: float = 0.0,
        y: float = 0.0,
        width: float = 300.0,
        height: float = 24.0,
        position: PositionInput = None,
        size: SizeInput = None,
        id: str | None = None,
        style: StyleInput = None,
        name: str | None = None,
        **style_values: Any,
    ) -> ReportBuilder:
        """Add a text object."""
        return self._add_text_object(
            text,
            x=x,
            y=y,
            width=width,
            height=height,
            position=position,
            size=size,
            id=id,
            style=style,
            name=name,
            role=None,
            default_style={},
            style_values=style_values,
        )

    def title(
        self,
        text: str,
        *,
        x: float = 50.0,
        y: float = 40.0,
        width: float = 500.0,
        height: float = 32.0,
        position: PositionInput = None,
        size: SizeInput = None,
        id: str | None = None,
        style: StyleInput = None,
        name: str | None = None,
        **style_values: Any,
    ) -> ReportBuilder:
        """Add a title text object and set metadata title."""
        self._report.metadata.title = text
        return self._add_text_object(
            text,
            x=x,
            y=y,
            width=width,
            height=height,
            position=position,
            size=size,
            id=id,
            style=style,
            name=name or "title",
            role="title",
            default_style={"font_size": 20, "bold": True},
            style_values=style_values,
        )

    def subtitle(
        self,
        text: str,
        *,
        x: float = 50.0,
        y: float = 72.0,
        width: float = 500.0,
        height: float = 24.0,
        position: PositionInput = None,
        size: SizeInput = None,
        id: str | None = None,
        style: StyleInput = None,
        name: str | None = None,
        **style_values: Any,
    ) -> ReportBuilder:
        """Add a subtitle text object and store metadata subtitle."""
        self._report.metadata.custom["subtitle"] = text
        return self._add_text_object(
            text,
            x=x,
            y=y,
            width=width,
            height=height,
            position=position,
            size=size,
            id=id,
            style=style,
            name=name or "subtitle",
            role="subtitle",
            default_style={"font_size": 14},
            style_values=style_values,
        )

    def header(
        self,
        text: str,
        *,
        x: float = 50.0,
        y: float = 24.0,
        width: float = 500.0,
        height: float = 18.0,
        position: PositionInput = None,
        size: SizeInput = None,
        id: str | None = None,
        style: StyleInput = None,
        name: str | None = None,
        **style_values: Any,
    ) -> ReportBuilder:
        """Add a header text object to the current page."""
        return self._add_text_object(
            text,
            x=x,
            y=y,
            width=width,
            height=height,
            position=position,
            size=size,
            id=id,
            style=style,
            name=name or "header",
            role="header",
            default_style={"font_size": 10, "bold": True},
            style_values=style_values,
        )

    def footer(
        self,
        text: str,
        *,
        x: float = 50.0,
        y: float | None = None,
        width: float = 500.0,
        height: float = 18.0,
        position: PositionInput = None,
        size: SizeInput = None,
        id: str | None = None,
        style: StyleInput = None,
        name: str | None = None,
        **style_values: Any,
    ) -> ReportBuilder:
        """Add a footer text object to the current page."""
        footer_y = _footer_y(self._ensure_current_page(), height) if y is None else y
        return self._add_text_object(
            text,
            x=x,
            y=footer_y,
            width=width,
            height=height,
            position=position,
            size=size,
            id=id,
            style=style,
            name=name or "footer",
            role="footer",
            default_style={"font_size": 10},
            style_values=style_values,
        )

    def field(
        self,
        binding: str,
        *,
        x: float = 0.0,
        y: float = 0.0,
        width: float = 300.0,
        height: float = 20.0,
        position: PositionInput = None,
        size: SizeInput = None,
        id: str | None = None,
        style: StyleInput = None,
        name: str | None = None,
        **style_values: Any,
    ) -> ReportBuilder:
        """Add a field object bound to a data expression."""
        obj = self._new_object(
            "field",
            id=id,
            x=x,
            y=y,
            width=width,
            height=height,
            position=position,
            size=size,
            style=style,
            style_values=style_values,
            name=name,
        )
        obj.binding = Binding(expression=binding)
        obj.properties["binding"] = binding
        self._report.add_object(obj)
        return self

    def line(
        self,
        *,
        x: float = 0.0,
        y: float = 0.0,
        width: float = 300.0,
        height: float = 0.0,
        position: PositionInput = None,
        size: SizeInput = None,
        id: str | None = None,
        style: StyleInput = None,
        name: str | None = None,
        **style_values: Any,
    ) -> ReportBuilder:
        """Add a line object."""
        obj = self._new_object(
            "line",
            id=id,
            x=x,
            y=y,
            width=width,
            height=height,
            position=position,
            size=size,
            style=style,
            style_values=style_values,
            name=name,
        )
        self._report.add_object(obj)
        return self

    def rectangle(
        self,
        *,
        x: float = 0.0,
        y: float = 0.0,
        width: float = 300.0,
        height: float = 100.0,
        position: PositionInput = None,
        size: SizeInput = None,
        id: str | None = None,
        style: StyleInput = None,
        name: str | None = None,
        **style_values: Any,
    ) -> ReportBuilder:
        """Add a rectangle object."""
        obj = self._new_object(
            "rectangle",
            id=id,
            x=x,
            y=y,
            width=width,
            height=height,
            position=position,
            size=size,
            style=style,
            style_values=style_values,
            name=name,
        )
        self._report.add_object(obj)
        return self

    def object(
        self,
        object_type: str,
        *,
        id: str | None = None,
        **properties: Any,
    ) -> ObjectBuilder:
        """Return an ObjectBuilder for a custom object type."""
        return ObjectBuilder(
            object_type,
            object_id=id or self._next_id(object_type),
            parent=self,
            **properties,
        )

    def style(self, name: str, style: StyleInput = None, **values: Any) -> ReportBuilder:
        """Add or replace a named style on the report."""
        report_style = _style_from(style)
        report_style.values.update(values)
        report_style.name = name
        self._report.styles[name] = report_style
        return self

    def style_builder(self, initial: StyleInput = None) -> StyleBuilder:
        """Return a standalone StyleBuilder."""
        return StyleBuilder(initial)

    def build(self) -> Report:
        """Return the built Report domain object."""
        return self._report

    def _new_object(
        self,
        object_type: str,
        *,
        id: str | None,
        x: float,
        y: float,
        width: float,
        height: float,
        position: PositionInput,
        size: SizeInput,
        style: StyleInput,
        style_values: Mapping[str, Any],
        name: str | None,
    ) -> Object:
        report_style = _style_from(style)
        report_style.values.update(style_values)
        properties: dict[str, Any] = {}
        if report_style.resolved_values():
            properties["style"] = report_style.to_dict()
        if name is not None:
            properties["name"] = name
        page_id = self._ensure_page_id(self._ensure_current_page())
        properties["page_id"] = page_id
        return Object(
            id=id or self._next_id(object_type),
            type=object_type,
            x=x,
            y=y,
            width=width,
            height=height,
            position=position,
            size=size,
            style=report_style,
            properties=properties,
        )

    def _add_text_object(
        self,
        text: str,
        *,
        x: float,
        y: float,
        width: float,
        height: float,
        position: PositionInput,
        size: SizeInput,
        id: str | None,
        style: StyleInput,
        name: str | None,
        role: str | None,
        default_style: Mapping[str, Any],
        style_values: Mapping[str, Any],
    ) -> ReportBuilder:
        obj = self._new_object(
            "text",
            id=id,
            x=x,
            y=y,
            width=width,
            height=height,
            position=position,
            size=size,
            style=_merge_style(style, default_style, style_values),
            style_values={},
            name=name,
        )
        obj.text = text
        obj.properties["text"] = text
        if role is not None:
            obj.properties["role"] = role
        self._report.add_object(obj)
        return self

    def _add_built_object(self, report_object: Object) -> None:
        page_id = self._ensure_page_id(self._ensure_current_page())
        report_object.properties.setdefault("page_id", page_id)
        self._report.add_object(report_object)

    def _ensure_current_page(self) -> Page:
        if self._current_page in self._report.pages:
            self._ensure_page_id(self._current_page)
            return self._current_page

        if self._report.pages:
            self._current_page = self._report.pages[-1]
        else:
            self._current_page = Page(id=self._next_id("page"))
            self._report.pages.append(self._current_page)
        self._ensure_page_id(self._current_page)
        return self._current_page

    def _create_page(
        self,
        *,
        size: str | None,
        width: float | None,
        height: float | None,
        unit: str | None,
        orientation: str,
        id: str | None,
    ) -> Page:
        default_page = Page()
        return Page(
            id=id or self._next_id("page"),
            width=default_page.width if width is None else width,
            height=default_page.height if height is None else height,
            unit=unit or ("px" if size else default_page.unit),
            orientation=orientation.lower(),
            size=size.lower() if size else None,
        )

    def _ensure_page_id(self, page: Page) -> str:
        if page.id is None:
            page.id = self._next_id("page")
        return page.id

    def _next_id(self, prefix: str) -> str:
        safe_prefix = _safe_id_prefix(prefix)
        while True:
            self._id_counts[safe_prefix] = self._id_counts.get(safe_prefix, 0) + 1
            candidate = f"{safe_prefix}_{self._id_counts[safe_prefix]}"
            if self._report.find(candidate) is None:
                return candidate


def _style_from(style: StyleInput) -> Style:
    if isinstance(style, Style):
        return style
    if isinstance(style, Mapping):
        return Style.from_dict(style)
    return Style()


def _merge_style(
    style: StyleInput,
    default_values: Mapping[str, Any],
    explicit_values: Mapping[str, Any],
) -> Style:
    base_style = _style_from(style)
    if not default_values and not explicit_values:
        return base_style

    if default_values:
        merged = Style(dict(default_values))
        if base_style.resolved_values():
            merged = merged.inherit(**base_style.resolved_values())
    else:
        merged = base_style

    if explicit_values:
        if merged.resolved_values():
            return merged.inherit(**explicit_values)
        return Style(dict(explicit_values))
    return merged


def _margin_from(
    top: float,
    right: float | None,
    bottom: float | None,
    left: float | None,
) -> Margin:
    resolved_right = top if right is None else right
    resolved_bottom = top if bottom is None else bottom
    resolved_left = resolved_right if left is None else left
    return Margin(
        top=top,
        right=resolved_right,
        bottom=resolved_bottom,
        left=resolved_left,
    )


def _footer_y(page: Page, height: float) -> float:
    return max(0.0, _page_height_hint(page) - _margin_bottom_hint(page) - height)


def _page_height_hint(page: Page) -> float:
    size = (page.size or "").lower()
    unit = page.unit.lower()
    if size == "letter" and unit == "px":
        return 816.0 if page.orientation.lower() == "landscape" else 1056.0
    if size == "a4" and unit == "px":
        return 793.7 if page.orientation.lower() == "landscape" else 1122.52
    return float(page.height)


def _margin_bottom_hint(page: Page) -> float:
    if page.size and page.unit.lower() == "px" and page.margin.bottom < 10:
        return page.margin.bottom * 96.0
    return page.margin.bottom


def _safe_id_prefix(value: str) -> str:
    prefix = "".join(char if char.isalnum() else "_" for char in value.lower()).strip("_")
    return prefix or "object"
