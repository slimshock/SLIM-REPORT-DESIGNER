"""Filesystem template storage provider."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from slim_report_core.serialization import JSONSerializer

from .base import TemplateRecord, record_from_summary, template_metadata, validate_template_id
from .errors import (
    TemplateNotFoundError,
    TemplatePermissionError,
    TemplateStorageError,
    TemplateValidationError,
)


class FileSystemTemplateProvider:
    """Filesystem-backed JSON template provider."""

    def __init__(
        self,
        template_folder: str | Path,
        *,
        allow_save: bool = False,
        allow_delete: bool = False,
    ) -> None:
        self.root = Path(template_folder)
        self.allow_save = allow_save
        self.allow_delete = allow_delete
        self.serializer = JSONSerializer()

    def ensure(self) -> None:
        """Create the template storage directory if needed."""
        self.root.mkdir(parents=True, exist_ok=True)

    def list_templates(self) -> list[dict[str, Any]]:
        """List saved templates as API-friendly summary dictionaries."""
        self.ensure()
        templates: list[dict[str, Any]] = []
        for path in sorted(self.root.glob("*.json")):
            template_id = path.stem
            try:
                template = self.get_template(template_id)
                summary = template_metadata(template_id, template)
            except TemplateStorageError:
                summary = {
                    "id": template_id,
                    "name": template_id,
                    "title": template_id,
                    "description": "",
                    "category": "",
                    "version": None,
                    "is_active": True,
                    "created_at": None,
                    "updated_at": None,
                }
            summary["path"] = path
            templates.append(summary)
        return templates

    def get_template(self, template_id: str) -> dict[str, Any]:
        """Load a template mapping by id."""
        path = self.path_for(template_id)
        if not path.exists():
            raise TemplateNotFoundError(f"Template not found: {template_id}")
        try:
            return self.serializer.dump_mapping(self.serializer.load(path))
        except TemplateStorageError:
            raise
        except Exception as exc:
            raise TemplateValidationError(f"Invalid template JSON: {template_id}") from exc

    def save_template(self, template_id: str, template: dict[str, Any]) -> dict[str, Any]:
        """Save a template mapping by id."""
        if not self.allow_save:
            raise TemplatePermissionError("Template saving is disabled.")
        path = self.path_for(template_id)
        self.ensure()
        try:
            report = self.serializer.load_mapping(template)
        except Exception as exc:
            raise TemplateValidationError(f"Invalid template: {template_id}") from exc
        self.serializer.save(report, path)
        return self.serializer.dump_mapping(report)

    def exists(self, template_id: str) -> bool:
        """Return whether a safe template id exists on disk."""
        try:
            return self.path_for(template_id).exists()
        except TemplateStorageError:
            return False

    def delete_template(self, template_id: str) -> bool:
        """Delete a template file when deletion is enabled."""
        if not self.allow_delete:
            raise TemplatePermissionError("Template deletion is disabled.")
        path = self.path_for(template_id)
        if not path.exists():
            raise TemplateNotFoundError(f"Template not found: {template_id}")
        path.unlink()
        return True

    def get_sample_data(self, template_id: str) -> dict[str, Any]:
        """Return embedded sample data for a template, if present."""
        template = self.get_template(template_id)
        data = template.get("data") if isinstance(template.get("data"), dict) else {}
        sample = data.get("sample") if isinstance(data, dict) else None
        return dict(sample) if isinstance(sample, dict) else {}

    def path_for(self, template_id: str) -> Path:
        """Resolve a template id to a safe JSON path."""
        safe_id = validate_template_id(template_id)
        return self.root / f"{safe_id}.json"


class TemplateStore(FileSystemTemplateProvider):
    """Backward-compatible JSON file storage for report templates."""

    def __init__(self, root: Path) -> None:
        super().__init__(root, allow_save=True, allow_delete=True)

    def list(self) -> list[TemplateRecord]:
        """List saved templates."""
        return [record_from_summary(item) for item in self.list_templates()]

    def get(self, template_id: str) -> TemplateRecord:
        """Return a saved template summary by id."""
        template = self.get_template(template_id)
        summary = template_metadata(template_id, template)
        summary["path"] = self.path_for(template_id)
        return record_from_summary(summary)

    def load_report(self, template_id: str):
        """Load a report by id."""
        return self.serializer.load_mapping(self.get_template(template_id))

    def save(self, template_id: str, report) -> None:
        """Save a report template by id."""
        self.save_template(template_id, self.serializer.dump_mapping(report))
