"""Report domain model."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .constants import DEFAULT_REPORT_VERSION
from .events import EventDispatcher, EventListener, ReportEvent
from .exceptions import ExporterError, ReportObjectNotFoundError, ReportValidationError
from .models import (
    Asset,
    Band,
    Layer,
    Metadata,
    Object,
    Page,
    ReportTemplate,
    Style,
)
from .validation import ReportValidationResult, validate_report

ObjectPredicate = Callable[[Object], bool]


class ReportObjectCollection(list[Object]):
    """List-like report object collection with query helpers."""

    def __call__(self, predicate: ObjectPredicate | None = None) -> list[Object]:
        """Return all objects, optionally filtered by predicate."""
        if predicate is None:
            return list(self)
        return [report_object for report_object in self if predicate(report_object)]

    def find(self, query: str | ObjectPredicate) -> Object | None:
        """Return the first object matching an id or predicate."""
        if callable(query):
            return _first(self(query))
        return _first(report_object for report_object in self if report_object.id == query)

    def find_by_name(self, name: str) -> Object | None:
        """Return the first object with a matching name property."""
        return _first(
            report_object for report_object in self if _object_name(report_object) == name
        )

    def of_type(
        self,
        object_type: str,
        predicate: ObjectPredicate | None = None,
    ) -> list[Object]:
        """Return objects of a specific type, optionally filtered by predicate."""
        objects = [report_object for report_object in self if report_object.type == object_type]
        if predicate is None:
            return objects
        return [report_object for report_object in objects if predicate(report_object)]


class ReportPageCollection(list[Page]):
    """List-like page collection that can be called for convenience."""

    def __call__(self) -> ReportPageCollection:
        """Return this page collection."""
        return self


class ReportAssetCollection(list[Asset]):
    """List-like asset collection that can be called for convenience."""

    def __call__(self) -> ReportAssetCollection:
        """Return this asset collection."""
        return self


class ReportStyleCollection(dict[str, Style]):
    """Dictionary-like style collection that can be called for convenience."""

    def __call__(
        self,
        name: str | None = None,
        style: Style | Mapping[str, Any] | None = None,
        **values: Any,
    ) -> ReportStyleCollection | Style:
        """Return styles or add/update a named style."""
        if name is None:
            return self

        if style is None:
            resolved = self.get(name, Style())
        elif isinstance(style, Style):
            resolved = style
        elif isinstance(style, Mapping):
            resolved = Style.from_dict(style)
        else:
            raise ReportValidationError("style must be a Style or mapping.")

        if values and resolved.resolved_values():
            resolved = resolved.inherit(**values)
        else:
            resolved.values.update(values)
        resolved.name = name
        self[name] = resolved
        return resolved


@dataclass(init=False)
class Report:
    """The central report domain model.

    Persistence formats, rendering, builders, adapters, and AI integrations
    should target this object rather than treating a serialized format as the
    source of truth.
    """

    version: str
    metadata: Metadata
    pages: ReportPageCollection
    objects: ReportObjectCollection
    bands: list[Band]
    layers: list[Layer]
    styles: ReportStyleCollection
    assets: ReportAssetCollection
    events: EventDispatcher

    def __init__(
        self,
        template: ReportTemplate | str | None = None,
        *,
        version: str = DEFAULT_REPORT_VERSION,
        metadata: Metadata | Mapping[str, Any] | None = None,
        pages: list[Page | Mapping[str, Any]] | None = None,
        page: Page | Mapping[str, Any] | None = None,
        objects: list[Object | Mapping[str, Any]] | None = None,
        bands: list[Band | Mapping[str, Any]] | None = None,
        layers: list[Layer | Mapping[str, Any]] | None = None,
        styles: Mapping[str, Style | Mapping[str, Any]] | None = None,
        assets: list[Asset | Mapping[str, Any]] | None = None,
    ) -> None:
        self.events = EventDispatcher()
        title = template if isinstance(template, str) else None
        if template is not None and not isinstance(template, str):
            self._load_template(template)
            return

        self.version = version
        self.metadata = _normalize_metadata(metadata)
        if title:
            self.metadata.title = title
        self.pages = _normalize_pages(pages, page)
        self._attach_pages()
        self.objects = _normalize_object_collection(objects)
        self.bands = [_normalize_band(item) for item in bands or []]
        self.layers = [_normalize_layer(item) for item in layers or []]
        self.styles = _normalize_styles(styles)
        self.assets = [_normalize_asset(item) for item in assets or []]

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "objects":
            value = _normalize_object_collection(value)
        elif name == "pages":
            value = _normalize_page_collection(value)
        elif name == "styles":
            value = _normalize_styles(value)
        elif name == "assets":
            value = _normalize_asset_collection(value)
        super().__setattr__(name, value)

    @property
    def page(self) -> Page:
        """Return the first page for single-page compatibility."""
        if not self.pages:
            self.pages.append(Page().attach(self))
        self.pages[0].attach(self)
        return self.pages[0]

    @property
    def template(self) -> ReportTemplate:
        """Return a legacy template adapter backed by this report's objects."""
        return ReportTemplate(
            version=self.version,
            metadata=self.metadata,
            page=self.page,
            objects=self.objects,
            bands=self.bands,
            assets=self.assets,
        )

    def render(
        self,
        data: Any = None,
        *,
        exporter: str = "html",
        context: Any = None,
    ) -> str | bytes:
        """Render this report with a named exporter."""
        self.emit("before_export", exporter=exporter, data=data, context=context)
        if exporter == "html":
            result = self.render_html(data)
        elif exporter == "pdf":
            result = self.render_pdf(data)
        else:
            raise ExporterError(f"Exporter is not registered: {exporter}.")
        self.emit("after_export", exporter=exporter, data=data, context=context, result=result)
        return result

    def render_html(self, data: Any = None) -> str:
        """Render this report as HTML."""
        from .rendering import render_html

        resolved_data = data or {}
        self.emit("before_render", format="html", data=resolved_data)
        result = render_html(self, resolved_data)
        self.emit("after_render", format="html", data=resolved_data, result=result)
        return result

    def render_pdf(self, data: Any = None) -> bytes:
        """Render this report as PDF bytes."""
        from .rendering import render_pdf

        resolved_data = data or {}
        self.emit("before_render", format="pdf", data=resolved_data)
        result = render_pdf(self, resolved_data)
        self.emit("after_render", format="pdf", data=resolved_data, result=result)
        return result

    def save_pdf(self, path: str | Path, data: Any = None, *, context: Any = None) -> None:
        """Render this report as PDF and save it to a file path."""
        rendered = self.render(data, exporter="pdf", context=context)
        if not isinstance(rendered, bytes):
            raise ExporterError("PDF exporter must return bytes.")
        Path(path).write_bytes(rendered)

    def save_html(self, path: str | Path, data: Any = None, *, context: Any = None) -> None:
        """Render this report as HTML and save it to a file path."""
        rendered = self.render(data, exporter="html", context=context)
        if isinstance(rendered, bytes):
            rendered = rendered.decode("utf-8")
        Path(path).write_text(rendered, encoding="utf-8")

    def validate(self) -> ReportValidationResult:
        """Validate this report and return structured validation errors."""
        return validate_report(self)

    def on(self, event_name: str, listener: EventListener) -> EventListener:
        """Register a listener for a report event."""
        return self.events.on(event_name, listener)

    def off(self, event_name: str, listener: EventListener) -> None:
        """Remove a listener for a report event."""
        self.events.off(event_name, listener)

    def emit(self, event_name: str, **payload: Any) -> ReportEvent:
        """Emit a report event."""
        return self.events.emit(event_name, self, **payload)

    def add_page(
        self,
        page: Page | Mapping[str, Any] | None = None,
        *,
        size: str | None = None,
        width: float | None = None,
        height: float | None = None,
        unit: str | None = None,
        orientation: str = "portrait",
        id: str | None = None,
    ) -> Page:
        """Add a page and return it."""
        if page is None:
            page = Page(
                id=id or f"page_{len(self.pages) + 1}",
                width=Page().width if width is None else width,
                height=Page().height if height is None else height,
                unit=unit or ("px" if size else Page().unit),
                orientation=orientation,
                size=size.lower() if size else None,
            )
        normalized = _normalize_page(page).attach(self)
        self.pages.append(normalized)
        self.emit("page_added", page=normalized)
        return normalized

    def new_page(
        self,
        size: str | None = None,
        *,
        width: float | None = None,
        height: float | None = None,
        unit: str | None = None,
        orientation: str = "portrait",
        id: str | None = None,
    ) -> Page:
        """Add a configured page and return it."""
        return self.add_page(
            size=size,
            width=width,
            height=height,
            unit=unit,
            orientation=orientation,
            id=id,
        )

    def remove_page(self, page_id_or_index: str | int) -> Page:
        """Remove and return a page by id or index."""
        if len(self.pages) <= 1:
            raise ReportValidationError("A report must contain at least one page.")

        index = self._page_index(page_id_or_index)
        removed = self.pages.pop(index)
        self.emit("page_removed", page=removed)
        return removed

    def add_object(self, report_object: Object | Mapping[str, Any]) -> Object:
        """Add a report object and return the normalized object instance."""
        normalized = _normalize_object(report_object)
        if self.find_object(normalized.id) is not None:
            raise ReportValidationError(f"Report object id already exists: {normalized.id}.")
        if "page_id" not in normalized.properties:
            page = self.page
            if page.id is None:
                page.id = f"page_{len(self.pages)}"
            normalized.properties["page_id"] = page.id

        self.objects.append(normalized)
        self.emit("object_added", object=normalized)
        return normalized

    def remove_object(self, object_id: str) -> Object:
        """Remove and return a report object by id."""
        for index, report_object in enumerate(self.objects):
            if report_object.id == object_id:
                removed = self.objects.pop(index)
                self.emit("object_removed", object=removed)
                return removed

        raise ReportObjectNotFoundError(f"Report object not found: {object_id}.")

    def find_object(self, object_id: str) -> Object | None:
        """Return a report object by id, or None when it does not exist."""
        return self.find(object_id)

    def get_object(self, object_id: str) -> Object | None:
        """Compatibility alias for :meth:`find_object`."""
        return self.find_object(object_id)

    def find(self, query: str | ObjectPredicate) -> Object | None:
        """Return the first object matching an id or predicate."""
        return self.objects.find(query)

    def find_by_name(self, name: str) -> Object | None:
        """Return the first object with a matching name property."""
        return self.objects.find_by_name(name)

    def text_objects(self, predicate: ObjectPredicate | None = None) -> list[Object]:
        """Return text objects, optionally filtered by predicate."""
        return self.objects.of_type("text", predicate)

    def fields(self, predicate: ObjectPredicate | None = None) -> list[Object]:
        """Return field objects, optionally filtered by predicate."""
        return self.objects.of_type("field", predicate)

    def images(self, predicate: ObjectPredicate | None = None) -> list[Object]:
        """Return image objects, optionally filtered by predicate."""
        return self.objects.of_type("image", predicate)

    def tables(self, predicate: ObjectPredicate | None = None) -> list[Object]:
        """Return table objects, optionally filtered by predicate."""
        return self.objects.of_type("table", predicate)

    def add_asset(self, asset: Asset | Mapping[str, Any]) -> Asset:
        """Add an asset and return it."""
        normalized = _normalize_asset(asset)
        if any(existing.id == normalized.id for existing in self.assets):
            raise ReportValidationError(f"Report asset id already exists: {normalized.id}.")
        self.assets.append(normalized)
        return normalized

    def clone(self, *, new_ids: bool = True, share_assets: bool = False) -> Report:
        """Return a deep clone of this report.

        Clones receive new ids by default. Pass ``new_ids=False`` to preserve
        page, object, band, layer, style, and asset ids. Pass
        ``share_assets=True`` to reuse the same asset objects instead of
        cloning them.
        """
        return self._clone(new_ids=new_ids, share_assets=share_assets)

    def copy(self) -> Report:
        """Return a deep copy of this report while preserving ids."""
        return self._clone(new_ids=False, share_assets=False)

    def _clone(self, *, new_ids: bool, share_assets: bool) -> Report:
        band_id_map: dict[str, str] = {}
        layer_id_map: dict[str, str] = {}
        style_id_map: dict[str, str] = {}
        asset_id_map: dict[str, str] = {}

        cloned_bands = [band.clone(new_ids=new_ids) for band in self.bands]
        for source, cloned in zip(self.bands, cloned_bands, strict=False):
            band_id_map[source.id] = cloned.id

        cloned_layers = [layer.clone(new_ids=new_ids) for layer in self.layers]
        for source, cloned in zip(self.layers, cloned_layers, strict=False):
            layer_id_map[source.id] = cloned.id

        cloned_styles: dict[str, Style] = {}
        for style_id, style in self.styles.items():
            cloned_style_id = _clone_style_id(style_id, new_ids=new_ids)
            style_id_map[style_id] = cloned_style_id
            cloned_styles[cloned_style_id] = style.clone()

        if share_assets:
            cloned_assets = list(self.assets)
        else:
            cloned_assets = [asset.clone(new_ids=new_ids) for asset in self.assets]
            for source, cloned in zip(self.assets, cloned_assets, strict=False):
                asset_id_map[source.id] = cloned.id

        cloned_objects = [
            _clone_object_with_reference_maps(
                report_object,
                new_ids=new_ids,
                band_id_map=band_id_map,
                layer_id_map=layer_id_map,
                style_id_map=style_id_map,
                asset_id_map=asset_id_map,
            )
            for report_object in self.objects
        ]

        return Report(
            version=self.version,
            metadata=self.metadata.clone(),
            pages=[page.clone(new_ids=new_ids) for page in self.pages],
            objects=cloned_objects,
            bands=cloned_bands,
            layers=cloned_layers,
            styles=cloned_styles,
            assets=cloned_assets,
        )

    def _load_template(self, template: ReportTemplate) -> None:
        if not isinstance(template, ReportTemplate):
            raise ReportValidationError("template must be a ReportTemplate.")
        self.version = template.version
        self.metadata = template.metadata
        self.pages = [template.page]
        self._attach_pages()
        self.objects = template.objects
        self.bands = template.bands
        self.layers = []
        self.styles = {}
        self.assets = template.assets

    def _copy_from(self, report: Report) -> None:
        self.version = report.version
        self.metadata = report.metadata
        self.pages = report.pages
        self._attach_pages()
        self.objects = report.objects
        self.bands = report.bands
        self.layers = report.layers
        self.styles = report.styles
        self.assets = report.assets

    def _page_index(self, page_id_or_index: str | int) -> int:
        if isinstance(page_id_or_index, int):
            if page_id_or_index < 0 or page_id_or_index >= len(self.pages):
                raise ReportValidationError(f"Report page index not found: {page_id_or_index}.")
            return page_id_or_index

        for index, page in enumerate(self.pages):
            if page.id == page_id_or_index:
                return index
        raise ReportValidationError(f"Report page not found: {page_id_or_index}.")

    def _attach_pages(self) -> None:
        for page in self.pages:
            page.attach(self)


def create_default_template() -> ReportTemplate:
    """Return a valid empty report template."""
    return Report().template


def _normalize_metadata(value: Metadata | Mapping[str, Any] | None) -> Metadata:
    if isinstance(value, Metadata):
        return value
    return Metadata.from_dict(value)


def _normalize_pages(
    pages: list[Page | Mapping[str, Any]] | None,
    page: Page | Mapping[str, Any] | None,
) -> ReportPageCollection:
    if pages is not None:
        normalized = [_normalize_page(item) for item in pages]
        return ReportPageCollection(normalized or [Page()])
    if page is not None:
        return ReportPageCollection([_normalize_page(page)])
    return ReportPageCollection([Page()])


def _normalize_page_collection(
    values: Iterable[Page | Mapping[str, Any]] | None,
) -> ReportPageCollection:
    if isinstance(values, ReportPageCollection):
        return values
    if values is None:
        return ReportPageCollection()
    if isinstance(values, Mapping) or not isinstance(values, Iterable):
        raise ReportValidationError("pages must be an iterable of Page instances or mappings.")
    return ReportPageCollection(_normalize_page(item) for item in values)


def _normalize_page(value: Page | Mapping[str, Any]) -> Page:
    if isinstance(value, Page):
        return value
    if isinstance(value, Mapping):
        return Page.from_dict(value)
    raise ReportValidationError("page must be a Page or mapping.")


def _normalize_object(value: Object | Mapping[str, Any]) -> Object:
    if isinstance(value, Object):
        return value
    if isinstance(value, Mapping):
        return Object.from_dict(value)
    raise ReportValidationError("report_object must be an Object or mapping.")


def _normalize_object_collection(
    values: Iterable[Object | Mapping[str, Any]] | None,
) -> ReportObjectCollection:
    if isinstance(values, ReportObjectCollection):
        return values
    if values is None:
        return ReportObjectCollection()
    if isinstance(values, Mapping) or not isinstance(values, Iterable):
        raise ReportValidationError("objects must be an iterable of Object instances or mappings.")
    return ReportObjectCollection(_normalize_object(item) for item in values)


def _normalize_band(value: Band | Mapping[str, Any]) -> Band:
    if isinstance(value, Band):
        return value
    if isinstance(value, Mapping):
        return Band.from_dict(value)
    raise ReportValidationError("band must be a Band or mapping.")


def _normalize_layer(value: Layer | Mapping[str, Any]) -> Layer:
    if isinstance(value, Layer):
        return value
    if isinstance(value, Mapping):
        return Layer.from_dict(value)
    raise ReportValidationError("layer must be a Layer or mapping.")


def _normalize_asset(value: Asset | Mapping[str, Any]) -> Asset:
    if isinstance(value, Asset):
        return value
    if isinstance(value, Mapping):
        return Asset.from_dict(value)
    raise ReportValidationError("asset must be an Asset or mapping.")


def _normalize_asset_collection(
    values: Iterable[Asset | Mapping[str, Any]] | None,
) -> ReportAssetCollection:
    if isinstance(values, ReportAssetCollection):
        return values
    if values is None:
        return ReportAssetCollection()
    if isinstance(values, Mapping) or not isinstance(values, Iterable):
        raise ReportValidationError("assets must be an iterable of Asset instances or mappings.")
    return ReportAssetCollection(_normalize_asset(item) for item in values)


def _normalize_styles(
    styles: Mapping[str, Style | Mapping[str, Any]] | None,
) -> ReportStyleCollection:
    if styles is None:
        return ReportStyleCollection()
    if isinstance(styles, ReportStyleCollection):
        return styles
    normalized: ReportStyleCollection = ReportStyleCollection()
    for style_id, style in styles.items():
        normalized_style = style if isinstance(style, Style) else Style.from_dict(style)
        normalized_style.name = str(style_id)
        normalized[str(style_id)] = normalized_style
    return normalized


def _clone_object_with_reference_maps(
    report_object: Object,
    *,
    new_ids: bool,
    band_id_map: Mapping[str, str],
    layer_id_map: Mapping[str, str],
    style_id_map: Mapping[str, str],
    asset_id_map: Mapping[str, str],
) -> Object:
    cloned = report_object.clone(new_ids=new_ids)
    if cloned.band_id in band_id_map:
        cloned.band_id = band_id_map[cloned.band_id]
    if cloned.layer_id in layer_id_map:
        cloned.layer_id = layer_id_map[cloned.layer_id]

    _remap_property_reference(cloned.properties, "band_id", band_id_map)
    _remap_property_reference(cloned.properties, "band", band_id_map)
    _remap_property_reference(cloned.properties, "layer_id", layer_id_map)
    _remap_property_reference(cloned.properties, "style_id", style_id_map)
    _remap_property_reference(cloned.properties, "asset_id", asset_id_map)
    return cloned


def _remap_property_reference(
    properties: dict[str, Any],
    key: str,
    id_map: Mapping[str, str],
) -> None:
    value = properties.get(key)
    if isinstance(value, str) and value in id_map:
        properties[key] = id_map[value]


def _clone_style_id(style_id: str, *, new_ids: bool) -> str:
    if not new_ids:
        return style_id
    return f"style_{uuid.uuid4().hex}"


def _object_name(report_object: Object) -> str | None:
    value = getattr(report_object, "name", None)
    if value is None:
        value = report_object.properties.get("name")
    if value is None:
        return None
    return str(value)


def _first(values: Iterable[Object]) -> Object | None:
    for value in values:
        return value
    return None
