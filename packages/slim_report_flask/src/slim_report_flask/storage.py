"""Template provider interfaces for the Flask adapter."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from slim_report_core import Report
from slim_report_core.serialization import JSONSerializer

_SAFE_TEMPLATE_ID = re.compile(r"^[A-Za-z0-9_.-]+$")


@dataclass(frozen=True)
class TemplateRecord:
    """Summary of a saved report template."""

    id: str
    title: str
    path: Path
    description: str = ""
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
        }

    def to_api_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.title,
            "title": self.title,
            "description": self.description,
            "updated_at": self.updated_at,
        }


class TemplateProvider(Protocol):
    """Template storage interface for Flask integrations."""

    def list_templates(self) -> list[dict[str, Any]]:
        """Return template summaries."""
        ...

    def get_template(self, template_id: str) -> dict[str, Any]:
        """Return a template mapping by id."""
        ...

    def save_template(self, template_id: str, template: dict[str, Any]) -> dict[str, Any]:
        """Persist and return a template mapping."""
        ...

    def exists(self, template_id: str) -> bool:
        """Return whether a template exists."""
        ...

    def delete_template(self, template_id: str) -> bool:
        """Delete a template if supported."""
        return False


class FileSystemTemplateProvider:
    """Filesystem-backed JSON template provider."""

    def __init__(self, root: str | Path, *, allow_save: bool = False) -> None:
        self.root = Path(root)
        self.allow_save = allow_save
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
                report = self.serializer.load(path)
                title = report.metadata.title or template_id
                description = getattr(report.metadata, "description", "") or ""
            except Exception:
                title = template_id
                description = ""
            templates.append(
                {
                    "id": template_id,
                    "name": title,
                    "title": title,
                    "description": description,
                    "updated_at": None,
                    "path": path,
                }
            )
        return templates

    def get_template(self, template_id: str) -> dict[str, Any]:
        """Load a template mapping by id."""
        path = self.path_for(template_id)
        if not path.exists():
            raise FileNotFoundError(f"Report template not found: {template_id}.")
        return self.serializer.dump_mapping(self.serializer.load(path))

    def save_template(self, template_id: str, template: dict[str, Any]) -> dict[str, Any]:
        """Save a template mapping by id."""
        if not self.allow_save:
            raise PermissionError("Template saving is disabled.")
        path = self.path_for(template_id)
        self.ensure()
        report = self.serializer.load_mapping(template)
        self.serializer.save(report, path)
        return self.serializer.dump_mapping(report)

    def exists(self, template_id: str) -> bool:
        """Return whether a safe template id exists on disk."""
        try:
            return self.path_for(template_id).exists()
        except ValueError:
            return False

    def delete_template(self, template_id: str) -> bool:
        """Delete a template file when saving is enabled."""
        if not self.allow_save:
            raise PermissionError("Template deletion is disabled.")
        path = self.path_for(template_id)
        if not path.exists():
            return False
        path.unlink()
        return True

    def path_for(self, template_id: str) -> Path:
        """Resolve a template id to a safe JSON path."""
        if not _SAFE_TEMPLATE_ID.fullmatch(template_id):
            raise ValueError(f"Invalid report template id: {template_id}.")
        return self.root / f"{template_id}.json"


class TemplateStore(FileSystemTemplateProvider):
    """Backward-compatible JSON file storage for report templates."""

    def __init__(self, root: Path) -> None:
        super().__init__(root, allow_save=True)

    def list(self) -> list[TemplateRecord]:
        """List saved templates."""
        return [_record_from_summary(item) for item in self.list_templates()]

    def get(self, template_id: str) -> TemplateRecord:
        """Return a saved template summary by id."""
        path = self.path_for(template_id)
        if not path.exists():
            raise FileNotFoundError(f"Report template not found: {template_id}.")
        template = self.get_template(template_id)
        metadata = template.get("metadata") if isinstance(template.get("metadata"), dict) else {}
        title = str(metadata.get("title") or metadata.get("name") or template_id)
        description = str(metadata.get("description") or "")
        return TemplateRecord(id=template_id, title=title, path=path, description=description)

    def load_report(self, template_id: str) -> Report:
        """Load a report by id."""
        return self.serializer.load_mapping(self.get_template(template_id))

    def save(self, template_id: str, report: Report) -> None:
        """Save a report template by id."""
        self.save_template(template_id, self.serializer.dump_mapping(report))


def _record_from_summary(summary: dict[str, Any]) -> TemplateRecord:
    template_id = str(summary.get("id") or "")
    title = str(summary.get("title") or summary.get("name") or template_id)
    path = summary.get("path")
    if not isinstance(path, Path):
        path = Path("")
    return TemplateRecord(
        id=template_id,
        title=title,
        path=path,
        description=str(summary.get("description") or ""),
        updated_at=summary.get("updated_at"),
    )
