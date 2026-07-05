"""Exporter registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..exceptions import ExporterError
from .base import BaseExporter


@dataclass
class ExporterRegistry:
    """Registry for named report exporters."""

    _exporters: dict[str, BaseExporter] = field(default_factory=dict)

    def register(self, name: str, exporter: BaseExporter) -> BaseExporter:
        """Register an exporter instance by name."""
        normalized_name = name.strip().lower()
        if not normalized_name:
            raise ExporterError("Exporter name must be a non-empty string.")
        if not isinstance(exporter, BaseExporter):
            raise ExporterError("Exporter must be a BaseExporter instance.")

        self._exporters[normalized_name] = exporter
        return exporter

    def get(self, name: str) -> BaseExporter | None:
        """Return a registered exporter, or None when it is not registered."""
        return self._exporters.get(name.strip().lower())

    def list(self) -> list[str]:
        """Return registered exporter names in stable order."""
        return sorted(self._exporters)

    def export(self, name: str, report: Any, data: Any = None, context: Any = None) -> Any:
        """Export a report using a named exporter."""
        exporter = self.get(name)
        if exporter is None:
            raise ExporterError(f"Exporter is not registered: {name}.")
        return exporter.export(report, data=data, context=context)


def create_default_exporter_registry() -> ExporterRegistry:
    """Create an exporter registry with built-in exporters."""
    from .html import HTMLExporter
    from .pdf import PDFExporter

    registry = ExporterRegistry()
    registry.register("html", HTMLExporter())
    registry.register("pdf", PDFExporter())
    return registry

