"""SQLAlchemy-backed template storage provider."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from slim_report_core.serialization import JSONSerializer

from .base import template_metadata, validate_template_id
from .errors import TemplateNotFoundError, TemplatePermissionError, TemplateValidationError


class SQLAlchemyTemplateProvider:
    """Generic SQLAlchemy template provider.

    The provider accepts a plain SQLAlchemy session or a Flask-SQLAlchemy session and a user-defined
    mapped model. SQLAlchemy is intentionally not imported at module import time.
    """

    def __init__(
        self,
        session: Any,
        model: type[Any],
        *,
        id_field: str = "template_id",
        name_field: str = "name",
        description_field: str = "description",
        category_field: str = "category",
        template_field: str = "template_json",
        sample_data_field: str = "sample_data_json",
        version_field: str = "version",
        active_field: str = "is_active",
        created_at_field: str = "created_at",
        updated_at_field: str = "updated_at",
        commit_on_save: bool = True,
        allow_save: bool = True,
        allow_delete: bool = False,
        json_dumps: Callable[[dict[str, Any]], str] | None = None,
        json_loads: Callable[[str], dict[str, Any]] | None = None,
    ) -> None:
        self.session = session
        self.model = model
        self.id_field = id_field
        self.name_field = name_field
        self.description_field = description_field
        self.category_field = category_field
        self.template_field = template_field
        self.sample_data_field = sample_data_field
        self.version_field = version_field
        self.active_field = active_field
        self.created_at_field = created_at_field
        self.updated_at_field = updated_at_field
        self.commit_on_save = commit_on_save
        self.allow_save = allow_save
        self.allow_delete = allow_delete
        self.json_dumps = json_dumps
        self.json_loads = json_loads
        self.serializer = JSONSerializer()

    def list_templates(self) -> list[dict[str, Any]]:
        """List stored active templates."""
        query = self.session.query(self.model)
        if self._has_field(self.active_field):
            query = query.filter(getattr(self.model, self.active_field) == True)  # noqa: E712
        return [self._metadata_for_record(record) for record in query.all()]

    def get_template(self, template_id: str) -> dict[str, Any]:
        """Load a template mapping by id."""
        record = self._get_record(template_id)
        if record is None:
            raise TemplateNotFoundError(f"Template not found: {template_id}")
        template = self._read_json_field(record, self.template_field)
        if not isinstance(template, dict):
            raise TemplateValidationError(f"Stored template is invalid: {template_id}")
        sample_data = self._sample_data_for_record(record)
        if sample_data:
            data = dict(template.get("data") or {})
            data["sample"] = sample_data
            template["data"] = data
        return self.serializer.dump_mapping(self.serializer.load_mapping(template))

    def save_template(self, template_id: str, template: dict[str, Any]) -> dict[str, Any]:
        """Create or update a template row."""
        if not self.allow_save:
            raise TemplatePermissionError("Template saving is disabled.")
        safe_id = validate_template_id(template_id)
        try:
            normalized = self.serializer.dump_mapping(self.serializer.load_mapping(template))
        except Exception as exc:
            raise TemplateValidationError(f"Invalid template: {template_id}") from exc

        record = self._get_record(safe_id, include_inactive=True)
        is_new = record is None
        if record is None:
            record = self.model()
            self._set_if_present(record, self.id_field, safe_id)
            self.session.add(record)

        metadata = template_metadata(safe_id, normalized)
        self._set_if_present(record, self.name_field, metadata["name"])
        self._set_if_present(record, self.description_field, metadata["description"])
        self._set_if_present(record, self.category_field, metadata["category"])
        self._set_if_present(record, self.template_field, normalized, json_value=True)

        sample_data = (
            normalized.get("data", {}).get("sample")
            if isinstance(normalized.get("data"), dict)
            else None
        )
        if isinstance(sample_data, dict) and self._has_field(self.sample_data_field):
            self._set_if_present(record, self.sample_data_field, sample_data, json_value=True)

        if self._has_field(self.version_field):
            current_version = getattr(record, self.version_field, None)
            next_version = (
                1 if is_new or not isinstance(current_version, int) else current_version + 1
            )
            setattr(record, self.version_field, next_version)
        self._set_if_present(record, self.active_field, True)
        now = datetime.now(timezone.utc)
        if is_new:
            self._set_if_present(record, self.created_at_field, now)
        self._set_if_present(record, self.updated_at_field, now)

        if self.commit_on_save:
            self.session.commit()
        return self.get_template(safe_id)

    def exists(self, template_id: str) -> bool:
        """Return whether a template exists."""
        try:
            return self._get_record(template_id) is not None
        except TemplateValidationError:
            return False

    def delete_template(self, template_id: str) -> bool:
        """Soft-delete or delete a template row."""
        if not self.allow_delete:
            raise TemplatePermissionError("Template deletion is disabled.")
        record = self._get_record(template_id)
        if record is None:
            raise TemplateNotFoundError(f"Template not found: {template_id}")
        if self._has_field(self.active_field):
            setattr(record, self.active_field, False)
            self._set_if_present(record, self.updated_at_field, datetime.now(timezone.utc))
        else:
            self.session.delete(record)
        if self.commit_on_save:
            self.session.commit()
        return True

    def get_sample_data(self, template_id: str) -> dict[str, Any]:
        """Return sample data stored separately or embedded in the template."""
        record = self._get_record(template_id)
        if record is None:
            raise TemplateNotFoundError(f"Template not found: {template_id}")
        sample = self._sample_data_for_record(record)
        if sample:
            return sample
        template = self._read_json_field(record, self.template_field)
        data = template.get("data") if isinstance(template.get("data"), dict) else {}
        embedded = data.get("sample") if isinstance(data, dict) else None
        return dict(embedded) if isinstance(embedded, dict) else {}

    def _get_record(self, template_id: str, *, include_inactive: bool = False) -> Any | None:
        safe_id = validate_template_id(template_id)
        if not self._has_field(self.id_field):
            raise TemplateValidationError(f"Model does not define id field: {self.id_field}")
        query = self.session.query(self.model).filter(getattr(self.model, self.id_field) == safe_id)
        if self._has_field(self.active_field) and not include_inactive:
            query = query.filter(getattr(self.model, self.active_field) == True)  # noqa: E712
        return query.first()

    def _metadata_for_record(self, record: Any) -> dict[str, Any]:
        template_id = str(self._get_if_present(record, self.id_field, ""))
        return {
            "id": template_id,
            "name": str(self._get_if_present(record, self.name_field, template_id) or template_id),
            "title": str(self._get_if_present(record, self.name_field, template_id) or template_id),
            "description": str(self._get_if_present(record, self.description_field, "") or ""),
            "category": str(self._get_if_present(record, self.category_field, "") or ""),
            "version": self._get_if_present(record, self.version_field, None),
            "is_active": bool(self._get_if_present(record, self.active_field, True)),
            "created_at": self._string_or_none(
                self._get_if_present(record, self.created_at_field, None)
            ),
            "updated_at": self._string_or_none(
                self._get_if_present(record, self.updated_at_field, None)
            ),
        }

    def _sample_data_for_record(self, record: Any) -> dict[str, Any]:
        if not self._has_field(self.sample_data_field):
            return {}
        value = self._read_json_field(record, self.sample_data_field)
        return dict(value) if isinstance(value, dict) else {}

    def _read_json_field(self, record: Any, field: str) -> Any:
        if not self._has_field(field):
            return {}
        value = getattr(record, field, None)
        if isinstance(value, str):
            if not value.strip():
                return {}
            loader = self.json_loads or json.loads
            return loader(value)
        return value if value is not None else {}

    def _set_if_present(
        self,
        record: Any,
        field: str,
        value: Any,
        *,
        json_value: bool = False,
    ) -> None:
        if not self._has_field(field):
            return
        if json_value and self._should_dump_json(record, field):
            dumper = self.json_dumps or json.dumps
            value = dumper(value)
        setattr(record, field, value)

    def _get_if_present(self, record: Any, field: str, default: Any) -> Any:
        if not self._has_field(field):
            return default
        return getattr(record, field, default)

    def _should_dump_json(self, record: Any, field: str) -> bool:
        current = getattr(record, field, None)
        return self.json_dumps is not None or isinstance(current, str) or field.endswith("_text")

    def _has_field(self, field: str) -> bool:
        return bool(field) and hasattr(self.model, field)

    def _string_or_none(self, value: Any) -> str | None:
        if value is None:
            return None
        if hasattr(value, "isoformat"):
            return str(value.isoformat())
        return str(value)
