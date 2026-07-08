"""Framework-agnostic template storage interfaces."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .errors import TemplateIdError

SAFE_TEMPLATE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")


@dataclass(frozen=True)
class TemplateRecord:
    """Summary of a saved report template."""

    id: str
    title: str
    path: Path = Path("")
    description: str = ""
    category: str = ""
    version: int | str | None = None
    is_active: bool = True
    created_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return the legacy compact Flask summary shape."""
        return {
            "id": self.id,
            "title": self.title,
        }

    def to_api_dict(self) -> dict[str, Any]:
        """Return the production API summary shape."""
        return {
            "id": self.id,
            "name": self.title,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "version": self.version,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class TemplateProvider(Protocol):
    """Template storage interface for framework adapters."""

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


def validate_template_id(template_id: str) -> str:
    """Validate and return a safe template id."""
    if not isinstance(template_id, str):
        raise TemplateIdError("Template id must be a string.")
    cleaned = template_id.strip()
    if not cleaned:
        raise TemplateIdError("Template id must not be empty.")
    if ":" in cleaned or "/" in cleaned or "\\" in cleaned or ".." in cleaned:
        raise TemplateIdError(f"Invalid report template id: {template_id}.")
    if not SAFE_TEMPLATE_ID_PATTERN.fullmatch(cleaned):
        raise TemplateIdError(f"Invalid report template id: {template_id}.")
    return cleaned


def record_from_summary(summary: dict[str, Any]) -> TemplateRecord:
    """Convert a provider summary mapping to a TemplateRecord."""
    template_id = str(summary.get("id") or summary.get("template_id") or "")
    title = str(summary.get("title") or summary.get("name") or template_id)
    path = summary.get("path")
    if not isinstance(path, Path):
        path = Path("")
    return TemplateRecord(
        id=template_id,
        title=title,
        path=path,
        description=str(summary.get("description") or ""),
        category=str(summary.get("category") or ""),
        version=summary.get("version"),
        is_active=bool(summary.get("is_active", True)),
        created_at=_string_or_none(summary.get("created_at")),
        updated_at=_string_or_none(summary.get("updated_at")),
    )


def template_metadata(template_id: str, template: dict[str, Any]) -> dict[str, Any]:
    """Return normalized metadata for a template mapping."""
    metadata = template.get("metadata") if isinstance(template.get("metadata"), dict) else {}
    custom = metadata.get("custom") if isinstance(metadata.get("custom"), dict) else {}
    return {
        "id": template_id,
        "name": str(metadata.get("title") or metadata.get("name") or template_id),
        "title": str(metadata.get("title") or metadata.get("name") or template_id),
        "description": str(metadata.get("description") or ""),
        "category": str(metadata.get("category") or custom.get("category") or ""),
        "version": metadata.get("version", 1),
        "is_active": True,
        "created_at": None,
        "updated_at": None,
    }


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    return str(value)
