"""Public report API for loading, editing, and serializing report templates."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from os import PathLike
from pathlib import Path
from typing import Any

from .exceptions import ExporterError, ReportObjectNotFoundError, ReportValidationError
from .models import ReportObject, ReportTemplate
from .rendering import render_html as render_template_html
from .rendering import render_pdf as render_template_pdf
from .utils import dump_json_object, parse_json_object

PathValue = str | PathLike[str]


@dataclass
class Report:
    """Editable report document backed by a serializable report template."""

    template: ReportTemplate = field(default_factory=ReportTemplate)

    @classmethod
    def load_from_dict(cls, data: Mapping[str, Any]) -> Report:
        """Create a report from a dictionary matching the report template shape."""
        return cls(template=ReportTemplate.from_dict(data))

    @classmethod
    def load_from_json(cls, payload: str | bytes | bytearray) -> Report:
        """Create a report from a JSON object string or bytes payload."""
        return cls.load_from_dict(parse_json_object(payload))

    @classmethod
    def load_json(cls, path: PathValue) -> Report:
        """Load a report template from a JSON file path."""
        return cls.load_from_json(Path(path).read_text(encoding="utf-8"))

    def to_dict(self) -> dict[str, Any]:
        """Return the report as a JSON-serializable dictionary."""
        return self.template.to_dict()

    def to_json(self, *, indent: int | None = 2) -> str:
        """Return the report as a JSON string."""
        return dump_json_object(self.to_dict(), indent=indent)

    def save_json(self, path: PathValue, *, indent: int | None = 2) -> None:
        """Save this report template to a JSON file path."""
        Path(path).write_text(self.to_json(indent=indent), encoding="utf-8")

    def render(
        self,
        data: Any = None,
        *,
        exporter: str = "html",
        context: Any = None,
    ) -> str | bytes:
        """Render this report with a named exporter."""
        if exporter == "html":
            return self.render_html(data)
        if exporter == "pdf":
            return self.render_pdf(data)
        raise ExporterError(f"Exporter is not registered: {exporter}.")

    def render_html(self, data: Any = None) -> str:
        """Render this report as HTML."""
        return render_template_html(self.to_dict(), data or {})

    def render_pdf(self, data: Any = None) -> bytes:
        """Render this report as PDF bytes."""
        return render_template_pdf(self.to_dict(), data or {})

    def save_pdf(self, path: PathValue, data: Any = None, *, context: Any = None) -> None:
        """Render this report as PDF and save it to a file path."""
        rendered = self.render(data, exporter="pdf", context=context)
        if not isinstance(rendered, bytes):
            raise ExporterError("PDF exporter must return bytes.")
        Path(path).write_bytes(rendered)

    def save_html(self, path: PathValue, data: Any = None, *, context: Any = None) -> None:
        """Render this report as HTML and save it to a file path."""
        rendered = self.render(data, exporter="html", context=context)
        if isinstance(rendered, bytes):
            rendered = rendered.decode("utf-8")
        Path(path).write_text(rendered, encoding="utf-8")

    def add_object(self, report_object: ReportObject | Mapping[str, Any]) -> ReportObject:
        """Add a report object and return the normalized object instance."""
        normalized = _normalize_report_object(report_object)
        if self.get_object(normalized.id) is not None:
            raise ReportValidationError(f"Report object id already exists: {normalized.id}.")

        self.template.objects.append(normalized)
        return normalized

    def remove_object(self, object_id: str) -> ReportObject:
        """Remove and return a report object by id."""
        for index, report_object in enumerate(self.template.objects):
            if report_object.id == object_id:
                return self.template.objects.pop(index)

        raise ReportObjectNotFoundError(f"Report object not found: {object_id}.")

    def get_object(self, object_id: str) -> ReportObject | None:
        """Return a report object by id, or None when it does not exist."""
        for report_object in self.template.objects:
            if report_object.id == object_id:
                return report_object
        return None


def create_default_template() -> ReportTemplate:
    """Return a valid empty report template."""
    return ReportTemplate()


def _normalize_report_object(report_object: ReportObject | Mapping[str, Any]) -> ReportObject:
    if isinstance(report_object, ReportObject):
        return report_object

    if isinstance(report_object, Mapping):
        return ReportObject.from_dict(report_object)

    raise ReportValidationError("report_object must be a ReportObject or mapping.")
