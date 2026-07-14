"""MySQL-specific query field discovery execution and metadata mapping."""

from __future__ import annotations

import logging
import socket
from collections.abc import Mapping, Sequence
from dataclasses import replace
from importlib import import_module
from time import monotonic

from sqlglot import Dialect
from sqlglot.tokens import Token, TokenType

from ...data_sources import MySQLConnectionConfig, ReportDataSource
from ...query_discovery import (
    DiscoveredColumn,
    ProviderFieldDiscoveryResult,
    QueryExecutionError,
    QueryExecutionTimeoutError,
    QueryFieldDiscoveryPolicy,
)
from .types import MySQLTypeMapper

logger = logging.getLogger(__name__)

_FIELD_TYPE_FALLBACKS = {
    0: "DECIMAL",
    1: "TINY",
    2: "SHORT",
    3: "LONG",
    4: "FLOAT",
    5: "DOUBLE",
    6: "NULL",
    7: "TIMESTAMP",
    8: "LONGLONG",
    9: "INT24",
    10: "DATE",
    11: "TIME",
    12: "DATETIME",
    15: "VARCHAR",
    16: "BIT",
    245: "JSON",
    246: "NEWDECIMAL",
    249: "TINY_BLOB",
    250: "MEDIUM_BLOB",
    251: "LONG_BLOB",
    252: "BLOB",
    253: "VAR_STRING",
    254: "STRING",
    255: "GEOMETRY",
}


class MySQLQueryFieldDiscovery:
    """Execute validated MySQL SELECT queries only far enough to inspect fields."""

    def __init__(
        self,
        provider: object,
        type_mapper: MySQLTypeMapper | None = None,
    ) -> None:
        self.provider = provider
        self.type_mapper = type_mapper or MySQLTypeMapper()

    def discover_query_fields(
        self,
        *,
        data_source: ReportDataSource,
        sql: str,
        parameters: Mapping[str, object],
        policy: QueryFieldDiscoveryPolicy,
    ) -> ProviderFieldDiscoveryResult:
        """Execute one validated query with bound parameters and read cursor metadata."""
        driver_sql = convert_mysql_named_placeholders(sql)
        started = monotonic()
        warnings: list[str] = []
        try:
            discovery_source = self._with_timeout(data_source, policy.execution_timeout_seconds)
            with self.provider.connection(discovery_source) as connection:  # type: ignore[attr-defined]
                cursor = None
                try:
                    cursor = connection.cursor()  # type: ignore[attr-defined]
                    cursor.execute(driver_sql, dict(parameters))
                    columns, column_warnings = self.columns_from_description(
                        getattr(cursor, "description", None)
                    )
                    warnings.extend(column_warnings)
                    rows = cursor.fetchmany(policy.max_preview_rows)
                    sample_row_count = len(rows or ())
                finally:
                    self._close_cursor(cursor)
        except Exception as exc:
            mapped = self._map_execution_error(exc)
            raise mapped from exc
        elapsed_ms = max(0.0, (monotonic() - started) * 1000.0)
        return ProviderFieldDiscoveryResult(
            columns=columns,
            sample_row_count=min(sample_row_count, policy.max_preview_rows),
            elapsed_ms=elapsed_ms,
            warnings=tuple(warnings),
        )

    def columns_from_description(
        self,
        description: object,
    ) -> tuple[tuple[DiscoveredColumn, ...], tuple[str, ...]]:
        """Convert DB-API cursor descriptions into immutable discovery metadata."""
        if description is None:
            return (), ("The MySQL cursor did not provide column metadata.",)
        if not isinstance(description, Sequence) or isinstance(
            description, (str, bytes, bytearray)
        ):
            raise QueryExecutionError("The MySQL cursor returned invalid column metadata.")

        labels = self._field_type_labels()
        columns: list[DiscoveredColumn] = []
        warnings: list[str] = []
        for index, item in enumerate(description, start=1):
            metadata = self._description_mapping(item)
            name = str(metadata.get("name") or "")
            type_code = metadata.get("type_code")
            database_type = labels.get(type_code, f"TYPE_{type_code}")
            normalized_type = self.type_mapper.normalize_driver_type(type_code, database_type)
            if normalized_type == "unknown":
                warnings.append(
                    f"Column {name or index!r} has unknown MySQL type {database_type!r}."
                )
            nullable = metadata.get("null_ok")
            if nullable is not None:
                nullable = bool(nullable)
            columns.append(
                DiscoveredColumn(
                    name=name,
                    ordinal_position=index,
                    database_type=database_type,
                    normalized_type=normalized_type,
                    nullable=nullable,
                    precision=self._optional_int(metadata.get("precision")),
                    scale=self._optional_int(metadata.get("scale")),
                    length=self._optional_int(metadata.get("length")),
                )
            )
        return tuple(columns), tuple(warnings)

    @staticmethod
    def _description_mapping(item: object) -> dict[str, object]:
        if isinstance(item, Mapping):
            return {
                "name": item.get("name") or item.get("column_name"),
                "type_code": item.get("type_code"),
                "length": item.get("internal_size", item.get("length")),
                "precision": item.get("precision"),
                "scale": item.get("scale"),
                "null_ok": item.get("null_ok"),
            }
        if isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray)):
            values = list(item)
            return {
                "name": values[0] if len(values) > 0 else None,
                "type_code": values[1] if len(values) > 1 else None,
                "length": values[3] if len(values) > 3 else None,
                "precision": values[4] if len(values) > 4 else None,
                "scale": values[5] if len(values) > 5 else None,
                "null_ok": values[6] if len(values) > 6 else None,
            }
        name = getattr(item, "name", None)
        if name is not None:
            return {
                "name": name,
                "type_code": getattr(item, "type_code", None),
                "length": getattr(item, "internal_size", None),
                "precision": getattr(item, "precision", None),
                "scale": getattr(item, "scale", None),
                "null_ok": getattr(item, "null_ok", None),
            }
        raise QueryExecutionError("The MySQL cursor returned invalid column metadata.")

    @staticmethod
    def _with_timeout(
        data_source: ReportDataSource,
        execution_timeout_seconds: int,
    ) -> ReportDataSource:
        config = getattr(data_source, "connection", None)
        if not isinstance(config, MySQLConnectionConfig):
            return data_source
        if config.query_timeout == execution_timeout_seconds:
            return data_source
        return ReportDataSource(
            id=data_source.id,
            name=data_source.name,
            type=data_source.type,
            connection=replace(config, query_timeout=execution_timeout_seconds),
        )

    @staticmethod
    def _field_type_labels() -> dict[object, str]:
        labels: dict[object, str] = dict(_FIELD_TYPE_FALLBACKS)
        try:
            field_type = import_module("pymysql.constants.FIELD_TYPE")
        except ImportError:
            return labels
        for name in dir(field_type):
            if name.startswith("_"):
                continue
            value = getattr(field_type, name)
            if isinstance(value, int):
                labels[value] = name
        return labels

    @staticmethod
    def _optional_int(value: object) -> int | None:
        if value is None or isinstance(value, bool):
            return None
        try:
            return int(value)
        except (TypeError, ValueError, OverflowError):
            return None

    @staticmethod
    def _map_execution_error(exc: Exception) -> Exception:
        if isinstance(exc, (QueryExecutionError, QueryExecutionTimeoutError)):
            return exc
        message = str(exc).lower()
        if (
            isinstance(exc, (TimeoutError, socket.timeout))
            or "timeout" in message
            or "timed out" in message
        ):
            return QueryExecutionTimeoutError(
                "The query timed out while discovering fields."
            )
        return QueryExecutionError("The query could not be executed for field discovery.")

    @staticmethod
    def _close_cursor(cursor: object | None) -> None:
        if cursor is None:
            return
        try:
            cursor.close()  # type: ignore[attr-defined]
        except Exception:
            logger.warning("A MySQL discovery cursor could not be closed cleanly.")


def convert_mysql_named_placeholders(sql: str) -> str:
    """Convert validated ``:name`` parameters to PyMySQL ``%(name)s`` placeholders."""
    tokenizer = Dialect.get_or_raise("mysql").tokenizer_class()
    tokens = tokenizer.tokenize(sql)
    chunks: list[str] = []
    cursor = 0
    index = 0
    while index < len(tokens):
        token = tokens[index]
        following = tokens[index + 1] if index + 1 < len(tokens) else None
        if _is_named_parameter(token, following):
            assert following is not None
            chunks.append(sql[cursor : token.start])
            chunks.append(f"%({following.text})s")
            cursor = following.end + 1
            index += 2
            continue
        index += 1
    chunks.append(sql[cursor:])
    return "".join(chunks)


def _is_named_parameter(token: Token, following: Token | None) -> bool:
    return (
        token.token_type is TokenType.COLON
        and following is not None
        and following.token_type is TokenType.VAR
        and token.end + 1 == following.start
    )
