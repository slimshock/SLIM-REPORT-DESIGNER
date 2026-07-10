"""JSON serializer for the report domain model."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ..data_sources import ReportDataset, ReportDataSource
from ..models import Asset, Band, Layer, Metadata, Page, Style
from ..object_factory import ObjectFactory
from ..report import Report
from ..schema import normalize_template_mapping, validate_template_mapping
from ..utils import dump_json_object, parse_json_object
from .base import BaseSerializer, PathValue


class JSONSerializer(BaseSerializer):
    """Convert JSON-compatible data to and from ``Report``."""

    def __init__(self, object_factory: ObjectFactory | None = None) -> None:
        self.object_factory = object_factory or ObjectFactory()

    def load_mapping(self, data: Mapping[str, Any]) -> Report:
        """Deserialize a JSON-compatible mapping into a report."""
        data = normalize_template_mapping(data)
        validate_template_mapping(data)
        metadata = Metadata.from_dict(data["metadata"])
        page = Page.from_dict(data["page"])
        pages = self._load_pages(data, page)
        objects = [self.object_factory.create_from_dict(item) for item in data["objects"]]
        bands = [Band.from_dict(item) for item in data["bands"]]
        assets = [Asset.from_dict(item) for item in data["assets"]]
        layers = [
            Layer.from_dict(item) for item in data.get("layers", []) if isinstance(item, Mapping)
        ]
        styles = self._load_styles(data.get("styles"))
        data_sources = [
            ReportDataSource.from_dict(item)
            for item in data.get("dataSources", [])
            if isinstance(item, Mapping)
        ]
        datasets = [
            ReportDataset.from_dict(item)
            for item in data.get("datasets", [])
            if isinstance(item, Mapping)
        ]

        return Report(
            version=str(data["version"]),
            metadata=metadata,
            pages=pages,
            objects=objects,
            bands=bands,
            layers=layers,
            styles=styles,
            assets=assets,
            data_sources=data_sources,
            datasets=datasets,
            data=dict(data.get("data", {})) if isinstance(data.get("data"), Mapping) else {},
        )

    def dump_mapping(self, report: Report) -> dict[str, Any]:
        """Serialize a report into a JSON-compatible mapping."""
        data = {
            "version": report.version,
            "metadata": report.metadata.to_dict(),
            "page": report.page.to_dict(),
            "objects": [item.to_dict() for item in report.objects],
            "bands": [item.to_dict() for item in report.bands],
            "assets": [item.to_dict() for item in report.assets],
        }
        if len(report.pages) > 1:
            data["pages"] = [item.to_dict() for item in report.pages]
        if report.layers:
            data["layers"] = [item.to_dict() for item in report.layers]
        if report.styles:
            data["styles"] = {
                style_id: style.to_dict() for style_id, style in report.styles.items()
            }
        if report.data_sources:
            data["dataSources"] = [item.to_dict() for item in report.data_sources]
        if report.datasets:
            data["datasets"] = [item.to_dict() for item in report.datasets]
        if getattr(report, "data", None):
            data["data"] = dict(report.data)
        return data

    def loads(self, payload: str | bytes | bytearray) -> Report:
        """Deserialize a JSON payload into a report."""
        return self.load_mapping(parse_json_object(payload))

    def dumps(self, report: Report, *, indent: int | None = 2) -> str:
        """Serialize a report into a JSON string."""
        return dump_json_object(self.dump_mapping(report), indent=indent)

    def load(self, path: PathValue) -> Report:
        """Deserialize a report from a JSON file path."""
        return self.loads(Path(path).read_text(encoding="utf-8"))

    def save(self, report: Report, path: PathValue, *, indent: int | None = 2) -> None:
        """Serialize a report to a JSON file path."""
        Path(path).write_text(self.dumps(report, indent=indent), encoding="utf-8")

    def _load_pages(self, data: Mapping[str, Any], fallback_page: Page) -> list[Page]:
        pages = data.get("pages")
        if isinstance(pages, list) and pages:
            return [Page.from_dict(item) for item in pages if isinstance(item, Mapping)]
        return [fallback_page]

    def _load_styles(self, data: Any) -> dict[str, Style]:
        if not isinstance(data, Mapping):
            return {}
        return {
            str(style_id): style if isinstance(style, Style) else Style.from_dict(style)
            for style_id, style in data.items()
            if isinstance(style, Mapping) or isinstance(style, Style)
        }
