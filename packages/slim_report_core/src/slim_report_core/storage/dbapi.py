"""DB-API template storage provider for MySQL-style connections."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from typing import Any

from slim_report_core.serialization import JSONSerializer

from .base import template_metadata, validate_template_id
from .errors import (
    TemplateNotFoundError,
    TemplatePermissionError,
    TemplateStorageError,
    TemplateValidationError,
)

_SAFE_TABLE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?$")


class DBAPITemplateProvider:
    """Template provider for MySQL-compatible Python DB-API connections.

    The application owns the connection factory. This provider does not import a concrete database
    driver, so PyMySQL and other DB-API packages remain optional.
    """

    def __init__(
        self,
        connection_factory: Callable[[], Any],
        *,
        table_name: str = "report_templates",
        allow_save: bool = False,
        allow_delete: bool = False,
        auto_ping: bool = True,
    ) -> None:
        self.connection_factory = connection_factory
        self.table_name = self._validate_table_name(table_name)
        self.allow_save = allow_save
        self.allow_delete = allow_delete
        self.auto_ping = auto_ping
        self.serializer = JSONSerializer()

    @classmethod
    def create_table_sql(cls, table_name: str = "report_templates") -> str:
        """Return the optional MySQL table schema for storing report templates."""
        table = cls._quote_table_name(cls._validate_table_name(table_name))
        return f"""CREATE TABLE IF NOT EXISTS {table} (
    id INT AUTO_INCREMENT PRIMARY KEY,
    template_id VARCHAR(120) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    description TEXT NULL,
    category VARCHAR(120) NULL,
    template_json LONGTEXT NOT NULL,
    sample_data_json LONGTEXT NULL,
    version INT NOT NULL DEFAULT 1,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME NULL,
    updated_at DATETIME NULL,
    INDEX idx_report_templates_template_id (template_id),
    INDEX idx_report_templates_active (is_active)
);"""

    def ensure_schema(self) -> None:
        """Create the storage table when explicitly called by the application."""
        conn = self._get_conn()
        try:
            self._execute(conn, self.create_table_sql(self.table_name))
            self._commit(conn)
        except TemplateStorageError:
            self._rollback(conn)
            raise
        except Exception as exc:
            self._rollback(conn)
            raise TemplateStorageError("Could not create report template table.") from exc

    def list_templates(self) -> list[dict[str, Any]]:
        """List active templates as API-friendly summary dictionaries."""
        rows = self._fetchall(
            f"""SELECT template_id, name, description, category, version, is_active,
created_at, updated_at
FROM {self._quoted_table}
WHERE is_active = 1
ORDER BY name, template_id"""
        )
        return [self._metadata_for_row(row) for row in rows]

    def get_template(self, template_id: str) -> dict[str, Any]:
        """Load one active template mapping by id."""
        row = self._get_row(template_id)
        if row is None:
            raise TemplateNotFoundError(f"Template not found: {template_id}")
        template = self._json_object(
            row.get("template_json"),
            f"Stored template is invalid: {template_id}",
        )
        sample_data = self._json_object(row.get("sample_data_json"), "")
        if sample_data:
            data = dict(template.get("data") or {})
            data["sample"] = sample_data
            template["data"] = data
        return self.serializer.dump_mapping(self.serializer.load_mapping(template))

    def save_template(self, template_id: str, template: dict[str, Any]) -> dict[str, Any]:
        """Insert or update one template row."""
        safe_id = validate_template_id(template_id)
        if not self.allow_save:
            raise TemplatePermissionError("Template saving is disabled.")
        try:
            normalized = self.serializer.dump_mapping(self.serializer.load_mapping(template))
        except Exception as exc:
            raise TemplateValidationError(f"Invalid template: {template_id}") from exc

        metadata = template_metadata(safe_id, normalized)
        sample_data = (
            normalized.get("data", {}).get("sample")
            if isinstance(normalized.get("data"), dict)
            else None
        )
        sample_json = self._dumps(sample_data if isinstance(sample_data, dict) else {})
        template_json = self._dumps(normalized)

        conn = self._get_conn()
        try:
            existing = self._get_row(safe_id, include_inactive=True, conn=conn)
            if existing is None:
                self._execute(
                    conn,
                    f"""INSERT INTO {self._quoted_table}
(template_id, name, description, category, template_json, sample_data_json,
version, is_active, created_at, updated_at)
VALUES (%s, %s, %s, %s, %s, %s, 1, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
                    (
                        safe_id,
                        metadata["name"],
                        metadata["description"],
                        metadata["category"],
                        template_json,
                        sample_json,
                    ),
                )
            else:
                self._execute(
                    conn,
                    f"""UPDATE {self._quoted_table}
SET name = %s,
    description = %s,
    category = %s,
    template_json = %s,
    sample_data_json = %s,
    version = COALESCE(version, 0) + 1,
    is_active = 1,
    updated_at = CURRENT_TIMESTAMP
WHERE template_id = %s""",
                    (
                        metadata["name"],
                        metadata["description"],
                        metadata["category"],
                        template_json,
                        sample_json,
                        safe_id,
                    ),
                )
            self._commit(conn)
        except TemplateStorageError:
            self._rollback(conn)
            raise
        except Exception as exc:
            self._rollback(conn)
            raise TemplateStorageError("Could not save report template.") from exc
        return self.get_template(safe_id)

    def exists(self, template_id: str) -> bool:
        """Return whether an active template row exists."""
        try:
            return self._get_row(template_id) is not None
        except TemplateValidationError:
            return False

    def delete_template(self, template_id: str) -> bool:
        """Soft-delete a template row by setting is_active to 0."""
        if not self.allow_delete:
            raise TemplatePermissionError("Template deletion is disabled.")
        safe_id = validate_template_id(template_id)
        if self._get_row(safe_id) is None:
            raise TemplateNotFoundError(f"Template not found: {template_id}")
        conn = self._get_conn()
        try:
            self._execute(
                conn,
                f"""UPDATE {self._quoted_table}
SET is_active = 0, updated_at = CURRENT_TIMESTAMP
WHERE template_id = %s""",
                (safe_id,),
            )
            self._commit(conn)
        except TemplateStorageError:
            self._rollback(conn)
            raise
        except Exception as exc:
            self._rollback(conn)
            raise TemplateStorageError("Could not delete report template.") from exc
        return True

    def get_sample_data(self, template_id: str) -> dict[str, Any]:
        """Return sample data stored separately or embedded in the template JSON."""
        row = self._get_row(template_id)
        if row is None:
            raise TemplateNotFoundError(f"Template not found: {template_id}")
        sample = self._json_object(row.get("sample_data_json"), "")
        if sample:
            return sample
        template = self._json_object(
            row.get("template_json"),
            f"Stored template is invalid: {template_id}",
        )
        data = template.get("data") if isinstance(template.get("data"), dict) else {}
        embedded = data.get("sample") if isinstance(data, dict) else None
        return dict(embedded) if isinstance(embedded, dict) else {}

    @property
    def _quoted_table(self) -> str:
        return self._quote_table_name(self.table_name)

    def _get_conn(self) -> Any:
        try:
            conn = self.connection_factory()
        except Exception as exc:
            raise TemplateStorageError("Could not connect to MySQL.") from exc
        if conn is None:
            raise TemplateStorageError("Could not connect to MySQL.")
        if self.auto_ping and hasattr(conn, "ping"):
            try:
                conn.ping(reconnect=True)
            except TypeError:
                try:
                    conn.ping()
                except Exception as exc:
                    raise TemplateStorageError("Could not connect to MySQL.") from exc
            except Exception as exc:
                raise TemplateStorageError("Could not connect to MySQL.") from exc
        return conn

    def _get_row(
        self,
        template_id: str,
        *,
        include_inactive: bool = False,
        conn: Any | None = None,
    ) -> dict[str, Any] | None:
        safe_id = validate_template_id(template_id)
        where = "template_id = %s" if include_inactive else "template_id = %s AND is_active = 1"
        if conn is None:
            conn = self._get_conn()
        return self._fetchone(
            f"""SELECT template_id, name, description, category, template_json,
sample_data_json, version, is_active, created_at, updated_at
FROM {self._quoted_table}
WHERE {where}
LIMIT 1""",
            (safe_id,),
            conn=conn,
        )

    def _fetchone(
        self,
        query: str,
        params: Sequence[Any] = (),
        *,
        conn: Any | None = None,
    ) -> dict[str, Any] | None:
        rows = self._fetch(query, params, conn=conn, one=True)
        return rows[0] if rows else None

    def _fetchall(
        self,
        query: str,
        params: Sequence[Any] = (),
        *,
        conn: Any | None = None,
    ) -> list[dict[str, Any]]:
        return self._fetch(query, params, conn=conn, one=False)

    def _fetch(
        self,
        query: str,
        params: Sequence[Any] = (),
        *,
        conn: Any | None,
        one: bool,
    ) -> list[dict[str, Any]]:
        if conn is None:
            conn = self._get_conn()
        cursor = self._cursor(conn)
        try:
            cursor.execute(query, tuple(params))
            row = cursor.fetchone() if one else None
            if one:
                return [] if row is None else [self._row_to_dict(cursor, row)]
            rows = cursor.fetchall()
            return [self._row_to_dict(cursor, item) for item in rows]
        except TemplateStorageError:
            raise
        except Exception as exc:
            raise TemplateStorageError("Could not query report templates.") from exc
        finally:
            self._close_if_supported(cursor)

    def _execute(
        self,
        conn: Any,
        query: str,
        params: Sequence[Any] = (),
    ) -> None:
        cursor = self._cursor(conn)
        try:
            cursor.execute(query, tuple(params))
        except Exception as exc:
            raise TemplateStorageError("Could not update report templates.") from exc
        finally:
            self._close_if_supported(cursor)

    def _cursor(self, conn: Any) -> Any:
        try:
            return conn.cursor()
        except Exception as exc:
            raise TemplateStorageError("Could not query report templates.") from exc

    def _metadata_for_row(self, row: dict[str, Any]) -> dict[str, Any]:
        template_id = str(row.get("template_id") or "")
        return {
            "id": template_id,
            "name": str(row.get("name") or template_id),
            "title": str(row.get("name") or template_id),
            "description": str(row.get("description") or ""),
            "category": str(row.get("category") or ""),
            "version": row.get("version"),
            "is_active": bool(row.get("is_active", True)),
            "created_at": self._string_or_none(row.get("created_at")),
            "updated_at": self._string_or_none(row.get("updated_at")),
        }

    def _json_object(self, value: Any, error_message: str) -> dict[str, Any]:
        if value is None or value == "":
            return {}
        if isinstance(value, (bytes, bytearray)):
            value = value.decode("utf-8")
        try:
            data = json.loads(value) if isinstance(value, str) else value
        except json.JSONDecodeError as exc:
            message = error_message or "Stored JSON is invalid."
            raise TemplateValidationError(message) from exc
        if isinstance(data, dict):
            return data
        if error_message:
            raise TemplateValidationError(error_message)
        return {}

    def _dumps(self, value: dict[str, Any]) -> str:
        return json.dumps(value, ensure_ascii=False)

    @staticmethod
    def _row_to_dict(cursor: Any, row: Any) -> dict[str, Any]:
        if isinstance(row, dict):
            return dict(row)
        description = getattr(cursor, "description", None) or ()
        columns = [str(column[0]) for column in description]
        return {column: row[index] for index, column in enumerate(columns)}

    @staticmethod
    def _commit(conn: Any) -> None:
        commit = getattr(conn, "commit", None)
        if callable(commit):
            commit()

    @staticmethod
    def _rollback(conn: Any) -> None:
        rollback = getattr(conn, "rollback", None)
        if callable(rollback):
            rollback()

    @staticmethod
    def _close_if_supported(value: Any) -> None:
        close = getattr(value, "close", None)
        if callable(close):
            close()

    @staticmethod
    def _string_or_none(value: Any) -> str | None:
        if value is None:
            return None
        if hasattr(value, "isoformat"):
            return str(value.isoformat())
        return str(value)

    @staticmethod
    def _validate_table_name(table_name: str) -> str:
        cleaned = str(table_name or "").strip()
        if not _SAFE_TABLE_NAME.fullmatch(cleaned):
            raise TemplateValidationError("Invalid report template table name.")
        return cleaned

    @staticmethod
    def _quote_table_name(table_name: str) -> str:
        return ".".join(f"`{part}`" for part in table_name.split("."))


class PyMySQLTemplateProvider(DBAPITemplateProvider):
    """Named DB-API provider for LIS apps that use raw PyMySQL connections."""
