"""File-backed template storage for the Flask adapter."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from slim_report_core import Report

_SAFE_TEMPLATE_ID = re.compile(r"^[A-Za-z0-9_.-]+$")


@dataclass(frozen=True)
class TemplateRecord:
    """Summary of a saved report template."""

    id: str
    title: str
    path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
        }


class TemplateStore:
    """JSON file storage for report templates."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def ensure(self) -> None:
        """Create the template storage directory if needed."""
        self.root.mkdir(parents=True, exist_ok=True)

    def list(self) -> list[TemplateRecord]:
        """List saved templates."""
        self.ensure()
        records = []
        for path in sorted(self.root.glob("*.json")):
            template_id = path.stem
            try:
                report = Report.load_json(path)
                title = report.template.metadata.title
            except Exception:
                title = template_id
            records.append(TemplateRecord(id=template_id, title=title, path=path))
        return records

    def get(self, template_id: str) -> TemplateRecord:
        """Return a saved template summary by id."""
        path = self.path_for(template_id)
        if not path.exists():
            raise FileNotFoundError(f"Report template not found: {template_id}.")
        report = Report.load_json(path)
        return TemplateRecord(id=template_id, title=report.template.metadata.title, path=path)

    def load_report(self, template_id: str) -> Report:
        """Load a report by id."""
        path = self.path_for(template_id)
        if not path.exists():
            raise FileNotFoundError(f"Report template not found: {template_id}.")
        return Report.load_json(path)

    def save(self, template_id: str, report: Report) -> None:
        """Save a report template by id."""
        path = self.path_for(template_id)
        self.ensure()
        report.save_json(path)

    def path_for(self, template_id: str) -> Path:
        """Resolve a template id to a safe JSON path."""
        if not _SAFE_TEMPLATE_ID.fullmatch(template_id):
            raise ValueError(f"Invalid report template id: {template_id}.")
        return self.root / f"{template_id}.json"

