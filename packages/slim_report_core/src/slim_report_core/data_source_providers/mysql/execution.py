"""MySQL-specific unbuffered dataset execution."""

from __future__ import annotations

import logging
import socket
from collections.abc import Mapping, Sequence
from threading import RLock
from typing import TYPE_CHECKING, Any

from ...dataset_execution.errors import (
    DatasetExecutionCancelledError,
    DatasetExecutionProviderError,
    DatasetExecutionTimeoutError,
    DatasetSchemaMismatchError,
)
from ...dataset_execution.provider import ProviderDatasetExecutionRequest
from ...query_discovery import QueryExecutionTimeoutError
from ..errors import (
    AuthenticationError,
    ConnectionTimeoutError,
    DatabaseUnavailableError,
    InvalidDatabaseError,
    ReadOnlySessionError,
)
from .discovery import convert_mysql_named_placeholders

if TYPE_CHECKING:
    from .provider import MySQLDataSourceProvider

logger = logging.getLogger(__name__)


def quote_mysql_identifier_part(value: str) -> str:
    """Quote one MySQL identifier part without treating prior quoting as trusted."""
    if not isinstance(value, str) or not value or "\x00" in value:
        raise DatasetExecutionProviderError("The MySQL identifier is invalid.")
    return f"`{value.replace('`', '``')}`"


def quote_mysql_qualified_identifier(value: str) -> str:
    """Quote every non-empty part of a dot-qualified MySQL identifier."""
    if not isinstance(value, str):
        raise DatasetExecutionProviderError("The MySQL identifier is invalid.")
    parts = value.split(".")
    if not parts or any(not part for part in parts):
        raise DatasetExecutionProviderError("The MySQL identifier is invalid.")
    return ".".join(quote_mysql_identifier_part(part) for part in parts)


def build_mysql_view_select(
    schema_name: str,
    view_name: str,
    fields: Sequence[object],
) -> str:
    """Build trusted SELECT SQL containing only explicitly quoted stored fields."""
    columns: list[str] = []
    for field in fields:
        name = getattr(field, "name", None)
        source_name = getattr(field, "source_name", None) or name
        if not isinstance(name, str) or not name:
            raise DatasetExecutionProviderError("The dataset contains an invalid field name.")
        if not isinstance(source_name, str) or not source_name:
            raise DatasetExecutionProviderError(
                "The dataset contains an invalid source field name."
            )
        column = quote_mysql_identifier_part(source_name)
        if source_name != name:
            column = f"{column} AS {quote_mysql_identifier_part(name)}"
        columns.append(column)
    if not columns:
        raise DatasetExecutionProviderError("The dataset has no fields to select.")
    relation = (
        f"{quote_mysql_identifier_part(schema_name)}.{quote_mysql_identifier_part(view_name)}"
    )
    return f"SELECT {', '.join(columns)} FROM {relation}"


class MySQLProviderDatasetRowStream:
    """Own one provider connection and one unbuffered cursor."""

    def __init__(
        self,
        provider: MySQLDataSourceProvider,
        request: ProviderDatasetExecutionRequest,
    ) -> None:
        self.provider = provider
        self._request: ProviderDatasetExecutionRequest | None = request
        self._source_type = request.source_type
        self._token = request.cancellation_token
        self._max_columns = request.max_columns
        self._require_unique_column_names = request.require_unique_column_names
        self.column_names: tuple[str, ...] = ()
        self._connection_context: Any = None
        self._connection: object | None = None
        self._cursor: object | None = None
        self._unregister = None
        self._closed = False
        self._lock = RLock()

    @classmethod
    def open(
        cls,
        provider: MySQLDataSourceProvider,
        request: ProviderDatasetExecutionRequest,
    ) -> MySQLProviderDatasetRowStream:
        stream = cls(provider, request)
        try:
            stream._open()
        except Exception:
            stream.close()
            raise
        return stream

    def fetchmany(self, size: int) -> Sequence[object]:
        """Fetch one raw bounded batch and conceal driver failures."""
        if self._closed or self._cursor is None:
            return ()
        token = self._token
        if token is not None and token.is_cancelled:
            self.close()
            raise DatasetExecutionCancelledError("Dataset execution was cancelled.")
        try:
            rows = self._cursor.fetchmany(size)  # type: ignore[attr-defined]
        except Exception as exc:
            if token is not None and token.is_cancelled:
                raise DatasetExecutionCancelledError("Dataset execution was cancelled.") from exc
            raise self._map_execution_error(exc) from exc
        return rows if rows is not None else ()

    def close(self) -> None:
        """Close the unbuffered cursor before its provider connection."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._request = None
            unregister = self._unregister
            self._unregister = None
            if unregister is not None:
                unregister()
            cursor = self._cursor
            self._cursor = None
            if cursor is not None:
                try:
                    cursor.close()  # type: ignore[attr-defined]
                except Exception:
                    logger.warning("A MySQL dataset cursor could not be closed cleanly.")
            context = self._connection_context
            self._connection_context = None
            self._connection = None
            if context is not None:
                try:
                    context.__exit__(None, None, None)
                except Exception:
                    logger.warning("A MySQL dataset connection could not be closed cleanly.")

    def _open(self) -> None:
        request = self._request
        if request is None:  # pragma: no cover - internal lifecycle guard
            raise DatasetExecutionProviderError("The dataset execution request is unavailable.")
        token = self._token
        if token is not None and token.is_cancelled:
            raise DatasetExecutionCancelledError("Dataset execution was cancelled.")
        context = self.provider.connection(request.data_source)
        try:
            self._connection = context.__enter__()
            self._connection_context = context
            if token is not None and token.is_cancelled:
                raise DatasetExecutionCancelledError("Dataset execution was cancelled.")
            cursor_class = self._unbuffered_cursor_class()
            self._cursor = self._connection.cursor(cursor_class)  # type: ignore[attr-defined]
            if token is not None:
                self._unregister = token._register(self.close)
            if token is not None and token.is_cancelled:
                raise DatasetExecutionCancelledError("Dataset execution was cancelled.")
            sql = request.sql
            if self._source_type == "query":
                sql = convert_mysql_named_placeholders(sql)
                self._cursor.execute(sql, dict(request.parameters))  # type: ignore[attr-defined]
            else:
                self._cursor.execute(sql)  # type: ignore[attr-defined]
            self.column_names = self._column_names(getattr(self._cursor, "description", None))
            self._request = None
        except Exception as exc:
            if token is not None and token.is_cancelled:
                raise DatasetExecutionCancelledError("Dataset execution was cancelled.") from exc
            if isinstance(
                exc,
                (
                    DatasetExecutionCancelledError,
                    DatasetExecutionProviderError,
                    DatasetExecutionTimeoutError,
                    DatasetSchemaMismatchError,
                ),
            ):
                raise
            raise self._map_execution_error(exc) from exc

    def _unbuffered_cursor_class(self) -> object:
        driver = self.provider._load_driver()
        cursor_module = getattr(driver, "cursors", None)
        cursor_class = getattr(cursor_module, "SSCursor", None)
        if cursor_class is None:
            raise DatasetExecutionProviderError(
                "The MySQL driver does not provide an unbuffered cursor."
            )
        return cursor_class

    def _column_names(self, description: object) -> tuple[str, ...]:
        if not isinstance(description, Sequence) or isinstance(
            description, (str, bytes, bytearray)
        ):
            raise DatasetSchemaMismatchError(
                "The dataset query did not return valid column metadata."
            )
        if not description:
            raise DatasetSchemaMismatchError("The dataset query did not return any columns.")
        if len(description) > self._max_columns:
            raise DatasetSchemaMismatchError(
                "The dataset query returned more columns than the execution limit."
            )
        names = tuple(self._description_name(item) for item in description)
        if self._require_unique_column_names:
            seen: set[str] = set()
            for name in names:
                normalized = name.casefold()
                if normalized in seen:
                    raise DatasetSchemaMismatchError(
                        f"The dataset query returned duplicate column '{name}'."
                    )
                seen.add(normalized)
        return names

    @staticmethod
    def _description_name(item: object) -> str:
        value: object = None
        if isinstance(item, Mapping):
            value = item.get("name") or item.get("column_name")
        elif isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray)):
            value = item[0] if item else None
        else:
            value = getattr(item, "name", None)
        if not isinstance(value, str) or not value:
            raise DatasetSchemaMismatchError("The dataset query returned invalid column metadata.")
        return value

    def _map_execution_error(self, exc: Exception) -> Exception:
        if isinstance(exc, DatasetExecutionCancelledError):
            return exc
        if isinstance(exc, (ConnectionTimeoutError, QueryExecutionTimeoutError)) or _is_timeout(
            exc
        ):
            return DatasetExecutionTimeoutError("Dataset execution timed out.")
        if isinstance(exc, AuthenticationError):
            return DatasetExecutionProviderError("MySQL authentication failed.")
        if isinstance(exc, InvalidDatabaseError):
            return DatasetExecutionProviderError(
                "The configured database does not exist or is not accessible."
            )
        if isinstance(exc, ReadOnlySessionError):
            return DatasetExecutionProviderError(
                "The MySQL session could not be verified as read-only."
            )
        if isinstance(exc, DatabaseUnavailableError):
            return DatasetExecutionProviderError(
                "The MySQL connection was lost during dataset execution."
            )
        code = exc.args[0] if exc.args and isinstance(exc.args[0], int) else None
        if code == 1045:
            return DatasetExecutionProviderError("MySQL authentication failed.")
        if code in {1044, 1049}:
            return DatasetExecutionProviderError(
                "The configured database does not exist or is not accessible."
            )
        if code in {2006, 2013}:
            return DatasetExecutionProviderError(
                "The MySQL connection was lost during dataset execution."
            )
        if self._source_type == "view" and code in {1142, 1146}:
            return DatasetExecutionProviderError("The configured reporting view is not available.")
        return DatasetExecutionProviderError("The dataset query could not be executed.")


def _is_timeout(exc: BaseException) -> bool:
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        if isinstance(current, (TimeoutError, socket.timeout)):
            return True
        message = str(current).casefold()
        if "timeout" in message or "timed out" in message:
            return True
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return False
