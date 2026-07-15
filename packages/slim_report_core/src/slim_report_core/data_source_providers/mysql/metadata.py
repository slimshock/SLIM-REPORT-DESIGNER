"""Provider-backed, views-only MySQL metadata discovery."""

from __future__ import annotations

import logging
import re
import socket
from collections.abc import Mapping, Sequence
from time import monotonic
from typing import Any

from ...data_sources import MySQLConnectionConfig, ReportDataSource
from ..errors import (
    ConnectionTimeoutError,
    DatabaseUnavailableError,
    InvalidDatabaseError,
    InvalidViewIdentifierError,
    MetadataAccessDeniedError,
    MetadataLimitExceededError,
    MetadataQueryError,
    UnsupportedMetadataOperationError,
    ViewNotFoundError,
)
from ..metadata import (
    DatabaseColumnInfo,
    DatabaseViewInfo,
    DatabaseViewSchema,
    MetadataAccessPolicy,
)
from .provider import MySQLDataSourceProvider
from .types import MySQLTypeMapper

logger = logging.getLogger(__name__)

_SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SYSTEM_SCHEMAS = frozenset({"information_schema", "mysql", "performance_schema", "sys"})

_VIEW_COLUMNS = (
    "TABLE_SCHEMA",
    "TABLE_NAME",
    "IS_UPDATABLE",
    "DEFINER",
    "SECURITY_TYPE",
)
_COLUMN_COLUMNS = (
    "TABLE_SCHEMA",
    "TABLE_NAME",
    "COLUMN_NAME",
    "ORDINAL_POSITION",
    "COLUMN_DEFAULT",
    "IS_NULLABLE",
    "DATA_TYPE",
    "COLUMN_TYPE",
    "CHARACTER_MAXIMUM_LENGTH",
    "NUMERIC_PRECISION",
    "NUMERIC_SCALE",
    "DATETIME_PRECISION",
    "COLUMN_COMMENT",
)

_LIST_VIEWS_SQL = """
SELECT
    TABLE_SCHEMA,
    TABLE_NAME,
    IS_UPDATABLE,
    DEFINER,
    SECURITY_TYPE
FROM information_schema.VIEWS
WHERE TABLE_SCHEMA = %s
ORDER BY TABLE_NAME
LIMIT %s
""".strip()

_GET_VIEW_SQL = """
SELECT
    TABLE_SCHEMA,
    TABLE_NAME,
    IS_UPDATABLE,
    DEFINER,
    SECURITY_TYPE
FROM information_schema.VIEWS
WHERE TABLE_SCHEMA = %s
  AND TABLE_NAME = %s
LIMIT 1
""".strip()

_LIST_COLUMNS_SQL = """
SELECT
    TABLE_SCHEMA,
    TABLE_NAME,
    COLUMN_NAME,
    ORDINAL_POSITION,
    COLUMN_DEFAULT,
    IS_NULLABLE,
    DATA_TYPE,
    COLUMN_TYPE,
    CHARACTER_MAXIMUM_LENGTH,
    NUMERIC_PRECISION,
    NUMERIC_SCALE,
    DATETIME_PRECISION,
    COLUMN_COMMENT
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = %s
  AND TABLE_NAME = %s
ORDER BY ORDINAL_POSITION
LIMIT %s
""".strip()


class MySQLMetadataService:
    """Discover approved MySQL views without executing report data queries."""

    def __init__(
        self,
        provider: MySQLDataSourceProvider,
        policy: MetadataAccessPolicy | None = None,
        type_mapper: MySQLTypeMapper | None = None,
    ) -> None:
        if getattr(provider, "provider_type", None) != "mysql":
            raise UnsupportedMetadataOperationError(
                "MySQL metadata requires a MySQL data-source provider."
            )
        self.provider = provider
        self.policy = policy or MetadataAccessPolicy()
        self.type_mapper = type_mapper or MySQLTypeMapper()
        if not self.policy.views_only:
            raise UnsupportedMetadataOperationError(
                "Sprint 7.4 supports metadata discovery for views only."
            )

    def list_views(self, data_source: ReportDataSource) -> tuple[DatabaseViewInfo, ...]:
        """List complete approved view metadata for the configured database."""
        schema = self._configured_schema(data_source)
        started = monotonic()
        logger.info("MySQL view metadata listing started for database %s.", schema)
        with self.provider.connection(data_source) as connection:
            rows = self._query_rows(
                connection,
                _LIST_VIEWS_SQL,
                (schema, self.policy.max_views + 1),
                _VIEW_COLUMNS,
            )
        if len(rows) > self.policy.max_views:
            raise MetadataLimitExceededError(
                f"View metadata exceeds the configured limit of {self.policy.max_views}."
            )
        views = tuple(
            self._convert_view(row) for row in rows if self._row_is_listable_view(row, schema)
        )
        ordered = tuple(sorted(views, key=lambda item: (item.view_name.casefold(), item.view_name)))
        logger.info(
            "MySQL view metadata listing returned %d views in %.3f ms.",
            len(ordered),
            self._elapsed_ms(started),
        )
        return ordered

    def get_view(self, data_source: ReportDataSource, view_name: str) -> DatabaseViewInfo:
        """Return one approved view or conceal it as not found."""
        schema, name = self._resolve_view_identifier(data_source, view_name)
        with self.provider.connection(data_source) as connection:
            return self._get_view_using_connection(connection, schema, name)

    def list_view_columns(
        self,
        data_source: ReportDataSource,
        view_name: str,
    ) -> tuple[DatabaseColumnInfo, ...]:
        """Return complete ordered metadata for an approved view's columns."""
        schema, name = self._resolve_view_identifier(data_source, view_name)
        with self.provider.connection(data_source) as connection:
            view = self._get_view_using_connection(connection, schema, name)
            return self._list_columns_using_connection(connection, view)

    def inspect_view(
        self,
        data_source: ReportDataSource,
        view_name: str,
    ) -> DatabaseViewSchema:
        """Inspect an approved view using one provider-owned connection."""
        schema, name = self._resolve_view_identifier(data_source, view_name)
        started = monotonic()
        logger.info("MySQL view metadata inspection started for %s.%s.", schema, name)
        with self.provider.connection(data_source) as connection:
            view = self._get_view_using_connection(connection, schema, name)
            columns = self._list_columns_using_connection(connection, view)
        logger.info(
            "MySQL view metadata inspection returned %d columns in %.3f ms.",
            len(columns),
            self._elapsed_ms(started),
        )
        return DatabaseViewSchema(view=view, columns=columns)

    def resolve_view_identifier(
        self,
        data_source: ReportDataSource,
        identifier: str,
    ) -> tuple[str, str]:
        """Structurally validate one view against the current access policy."""
        schema, view_name = self._resolve_view_identifier(data_source, identifier)
        if not self._view_is_allowed(view_name):
            raise MetadataAccessDeniedError(
                "The configured reporting view is not available for execution."
            )
        return schema, view_name

    def _get_view_using_connection(
        self,
        connection: object,
        schema: str,
        view_name: str,
    ) -> DatabaseViewInfo:
        if not self._view_is_allowed(view_name):
            raise self._view_not_found(view_name)
        rows = self._query_rows(
            connection,
            _GET_VIEW_SQL,
            (schema, view_name),
            _VIEW_COLUMNS,
        )
        if not rows:
            raise self._view_not_found(view_name)
        row = rows[0]
        if not self._row_is_requested_view(row, schema, view_name):
            raise self._view_not_found(view_name)
        return self._convert_view(row)

    def _list_columns_using_connection(
        self,
        connection: object,
        view: DatabaseViewInfo,
    ) -> tuple[DatabaseColumnInfo, ...]:
        rows = self._query_rows(
            connection,
            _LIST_COLUMNS_SQL,
            (view.schema_name, view.view_name, self.policy.max_columns_per_view + 1),
            _COLUMN_COLUMNS,
        )
        if len(rows) > self.policy.max_columns_per_view:
            raise MetadataLimitExceededError(
                "Column metadata exceeds the configured limit of "
                f"{self.policy.max_columns_per_view}."
            )
        columns = tuple(
            self._convert_column(row, view)
            for row in rows
            if self._row_matches_object(row, view.schema_name, view.view_name)
        )
        return tuple(sorted(columns, key=lambda item: item.ordinal_position))

    def _query_rows(
        self,
        connection: object,
        sql: str,
        parameters: tuple[object, ...],
        column_names: tuple[str, ...],
    ) -> tuple[dict[str, Any], ...]:
        cursor = None
        try:
            cursor = connection.cursor()  # type: ignore[attr-defined]
            cursor.execute(sql, parameters)
            raw_rows = cursor.fetchall()
        except Exception as exc:
            raise self._map_query_error(exc) from exc
        finally:
            self._close_cursor(cursor)
        if raw_rows is None:
            return ()
        if not isinstance(raw_rows, Sequence) or isinstance(raw_rows, (str, bytes, bytearray)):
            raise MetadataQueryError("The MySQL metadata query returned an invalid row collection.")
        return tuple(self._row_mapping(row, column_names) for row in raw_rows)

    @staticmethod
    def _row_mapping(row: object, column_names: tuple[str, ...]) -> dict[str, Any]:
        if isinstance(row, Mapping):
            return {str(key).upper(): value for key, value in row.items()}
        if isinstance(row, Sequence) and not isinstance(row, (str, bytes, bytearray)):
            if len(row) < len(column_names):
                raise MetadataQueryError("The MySQL metadata query returned an invalid row shape.")
            return dict(zip(column_names, row, strict=False))
        raise MetadataQueryError("The MySQL metadata query returned an invalid row shape.")

    def _convert_view(self, row: Mapping[str, Any]) -> DatabaseViewInfo:
        schema = self._required_text(row, "TABLE_SCHEMA")
        name = self._required_text(row, "TABLE_NAME")
        include_details = self.policy.include_updatable_metadata
        return DatabaseViewInfo(
            schema_name=schema,
            view_name=name,
            display_name=name,
            is_updatable=self._yes_no(row.get("IS_UPDATABLE")) if include_details else None,
            definer=self._optional_text(row.get("DEFINER")) if include_details else None,
            security_type=self._optional_text(row.get("SECURITY_TYPE"))
            if include_details
            else None,
        )

    def _convert_column(
        self,
        row: Mapping[str, Any],
        view: DatabaseViewInfo,
    ) -> DatabaseColumnInfo:
        name = self._required_text(row, "COLUMN_NAME")
        ordinal = self._required_positive_int(row, "ORDINAL_POSITION")
        data_type = self._required_text(row, "DATA_TYPE")
        column_type = self._optional_text(row.get("COLUMN_TYPE")) or data_type
        nullable = self._required_nullable(row.get("IS_NULLABLE"))
        character_length = self._optional_int(row.get("CHARACTER_MAXIMUM_LENGTH"))
        numeric_precision = self._optional_int(row.get("NUMERIC_PRECISION"))
        numeric_scale = self._optional_int(row.get("NUMERIC_SCALE"))
        datetime_precision = self._optional_int(row.get("DATETIME_PRECISION"))
        normalized_type = self.type_mapper.normalize(
            data_type=data_type,
            column_type=column_type,
            numeric_precision=numeric_precision,
            numeric_scale=numeric_scale,
            character_maximum_length=character_length,
            datetime_precision=datetime_precision,
        )
        return DatabaseColumnInfo(
            name=name,
            ordinal_position=ordinal,
            database_type=column_type,
            normalized_type=normalized_type,
            nullable=nullable,
            default=row.get("COLUMN_DEFAULT"),
            character_maximum_length=character_length,
            numeric_precision=numeric_precision,
            numeric_scale=numeric_scale,
            datetime_precision=datetime_precision,
            column_comment=self._optional_text(row.get("COLUMN_COMMENT")),
            source_name=name,
        )

    def _configured_schema(self, data_source: ReportDataSource) -> str:
        config = getattr(data_source, "connection", None)
        if not isinstance(config, MySQLConnectionConfig):
            raise InvalidViewIdentifierError(
                "The MySQL data source does not contain a valid database configuration."
            )
        schema = config.database
        if not isinstance(schema, str) or _SAFE_IDENTIFIER_RE.fullmatch(schema) is None:
            raise InvalidViewIdentifierError("The configured database identifier is invalid.")
        if self._is_system_schema(schema) and not self.policy.include_system_schemas:
            raise MetadataAccessDeniedError("System-schema metadata access is not allowed.")
        return schema

    def _resolve_view_identifier(
        self,
        data_source: ReportDataSource,
        identifier: str,
    ) -> tuple[str, str]:
        configured_schema = self._configured_schema(data_source)
        if not isinstance(identifier, str) or not identifier:
            raise InvalidViewIdentifierError("The view identifier is invalid.")
        parts = identifier.split(".")
        if len(parts) not in {1, 2} or any(
            _SAFE_IDENTIFIER_RE.fullmatch(part) is None for part in parts
        ):
            raise InvalidViewIdentifierError("The view identifier is invalid.")
        if len(parts) == 1:
            return configured_schema, parts[0]
        if not self.policy.allow_cross_schema:
            raise MetadataAccessDeniedError("Cross-schema metadata access is not allowed.")
        schema, name = parts
        allowed_schemas = {item.casefold() for item in self.policy.allowed_schemas}
        if schema.casefold() not in allowed_schemas:
            raise MetadataAccessDeniedError("Cross-schema metadata access is not allowed.")
        if self._is_system_schema(schema) and not self.policy.include_system_schemas:
            raise MetadataAccessDeniedError("System-schema metadata access is not allowed.")
        return schema, name

    def _row_is_listable_view(self, row: Mapping[str, Any], schema: str) -> bool:
        try:
            row_schema = self._required_text(row, "TABLE_SCHEMA")
            name = self._required_text(row, "TABLE_NAME")
        except MetadataQueryError:
            raise
        return (
            row_schema.casefold() == schema.casefold()
            and (self.policy.include_system_schemas or not self._is_system_schema(row_schema))
            and self._view_is_allowed(name)
        )

    def _row_is_requested_view(
        self,
        row: Mapping[str, Any],
        schema: str,
        view_name: str,
    ) -> bool:
        row_schema = self._required_text(row, "TABLE_SCHEMA")
        row_name = self._required_text(row, "TABLE_NAME")
        return (
            row_schema.casefold() == schema.casefold()
            and row_name.casefold() == view_name.casefold()
            and (self.policy.include_system_schemas or not self._is_system_schema(row_schema))
            and self._view_is_allowed(row_name)
        )

    def _row_matches_object(
        self,
        row: Mapping[str, Any],
        schema: str,
        view_name: str,
    ) -> bool:
        row_schema = self._required_text(row, "TABLE_SCHEMA")
        row_name = self._required_text(row, "TABLE_NAME")
        return (
            row_schema.casefold() == schema.casefold()
            and row_name.casefold() == view_name.casefold()
        )

    def _view_is_allowed(self, view_name: str) -> bool:
        exact = {item.casefold() for item in self.policy.allowed_view_names}
        prefixes = tuple(item.casefold() for item in self.policy.allowed_view_prefixes)
        if not exact and not prefixes:
            return True
        normalized = view_name.casefold()
        return normalized in exact or normalized.startswith(prefixes)

    def _is_system_schema(self, schema: str) -> bool:
        return schema.casefold() in _SYSTEM_SCHEMAS

    @staticmethod
    def _view_not_found(view_name: str) -> ViewNotFoundError:
        return ViewNotFoundError(f"The reporting view {view_name!r} was not found.")

    @staticmethod
    def _required_text(row: Mapping[str, Any], key: str) -> str:
        value = row.get(key)
        if not isinstance(value, str) or not value:
            raise MetadataQueryError(f"The MySQL metadata row is missing required field {key}.")
        return value

    @staticmethod
    def _optional_text(value: object) -> str | None:
        if value is None:
            return None
        return str(value)

    @staticmethod
    def _required_positive_int(row: Mapping[str, Any], key: str) -> int:
        value = MySQLMetadataService._optional_int(row.get(key))
        if value is None or value < 1:
            raise MetadataQueryError(f"The MySQL metadata row contains an invalid value for {key}.")
        return value

    @staticmethod
    def _optional_int(value: object) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool):
            raise MetadataQueryError("The MySQL metadata row contains invalid numeric metadata.")
        try:
            return int(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise MetadataQueryError(
                "The MySQL metadata row contains invalid numeric metadata."
            ) from exc

    @staticmethod
    def _required_nullable(value: object) -> bool:
        if isinstance(value, bool):
            return value
        normalized = str(value).strip().upper()
        if normalized == "YES":
            return True
        if normalized == "NO":
            return False
        raise MetadataQueryError("The MySQL metadata row contains an invalid nullable value.")

    @staticmethod
    def _yes_no(value: object) -> bool | None:
        if value is None:
            return None
        normalized = str(value).strip().upper()
        if normalized == "YES":
            return True
        if normalized == "NO":
            return False
        return None

    @staticmethod
    def _map_query_error(exc: Exception) -> Exception:
        code = exc.args[0] if exc.args and isinstance(exc.args[0], int) else None
        message = str(exc).lower()
        if (
            isinstance(exc, (TimeoutError, socket.timeout))
            or "timeout" in message
            or "timed out" in message
        ):
            return ConnectionTimeoutError("The MySQL metadata query timed out.")
        if code in {1044, 1045, 1142, 1227}:
            return MetadataAccessDeniedError(
                "The configured MySQL account cannot read view metadata."
            )
        if code == 1049:
            return InvalidDatabaseError(
                "The configured database does not exist or is not accessible."
            )
        if code in {2002, 2003, 2006, 2013}:
            return DatabaseUnavailableError("The MySQL connection was lost during metadata access.")
        return MetadataQueryError("The MySQL metadata query failed.")

    @staticmethod
    def _close_cursor(cursor: object | None) -> None:
        if cursor is None:
            return
        try:
            cursor.close()  # type: ignore[attr-defined]
        except Exception:
            logger.warning("A MySQL metadata cursor could not be closed cleanly.")

    @staticmethod
    def _elapsed_ms(started: float) -> float:
        return max(0.0, (monotonic() - started) * 1000.0)
