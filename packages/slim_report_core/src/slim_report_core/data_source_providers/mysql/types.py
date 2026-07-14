"""Deterministic MySQL-to-report field type normalization."""

from __future__ import annotations

import re
from typing import ClassVar


class MySQLTypeMapper:
    """Map MySQL and MariaDB column types to Sprint 7.1 field types."""

    _STRING_TYPES = frozenset(
        {"char", "varchar", "tinytext", "text", "mediumtext", "longtext", "enum", "set", "json"}
    )
    _INTEGER_TYPES = frozenset(
        {"tinyint", "smallint", "mediumint", "int", "integer", "bigint", "year"}
    )
    _FLOAT_TYPES = frozenset({"float", "double", "real"})
    _DECIMAL_TYPES = frozenset({"decimal", "numeric", "dec", "fixed"})
    _BOOLEAN_TYPES = frozenset({"bool", "boolean"})
    _BINARY_TYPES = frozenset(
        {"binary", "varbinary", "tinyblob", "blob", "mediumblob", "longblob", "bit"}
    )
    _TINYINT_ONE_RE = re.compile(r"^tinyint\s*\(\s*1\s*\)", re.IGNORECASE)
    _DRIVER_TYPE_MAP: ClassVar[dict[str, str]] = {
        "VAR_STRING": "string",
        "STRING": "string",
        "VARCHAR": "string",
        "TINY": "integer",
        "SHORT": "integer",
        "LONG": "integer",
        "LONGLONG": "integer",
        "INT24": "integer",
        "YEAR": "integer",
        "FLOAT": "float",
        "DOUBLE": "float",
        "DECIMAL": "decimal",
        "NEWDECIMAL": "decimal",
        "DATE": "date",
        "NEWDATE": "date",
        "TIME": "time",
        "DATETIME": "datetime",
        "TIMESTAMP": "datetime",
        "TINY_BLOB": "binary",
        "MEDIUM_BLOB": "binary",
        "LONG_BLOB": "binary",
        "BLOB": "binary",
        "BIT": "binary",
        "JSON": "string",
        "NULL": "unknown",
        "GEOMETRY": "unknown",
    }

    def normalize(
        self,
        data_type: str,
        column_type: str | None = None,
        numeric_precision: int | None = None,
        numeric_scale: int | None = None,
        character_maximum_length: int | None = None,
        datetime_precision: int | None = None,
    ) -> str:
        """Return a supported report type without raising for future MySQL types."""
        del numeric_precision, numeric_scale, character_maximum_length, datetime_precision
        normalized = str(data_type or "").strip().lower()
        original_column_type = str(column_type or "").strip()
        if normalized == "tinyint" and self._TINYINT_ONE_RE.match(original_column_type):
            return "boolean"
        if normalized in self._STRING_TYPES:
            return "string"
        if normalized in self._INTEGER_TYPES:
            return "integer"
        if normalized in self._FLOAT_TYPES:
            return "float"
        if normalized in self._DECIMAL_TYPES:
            return "decimal"
        if normalized in self._BOOLEAN_TYPES:
            return "boolean"
        if normalized == "date":
            return "date"
        if normalized == "time":
            return "time"
        if normalized in {"datetime", "timestamp"}:
            return "datetime"
        if normalized in self._BINARY_TYPES:
            return "binary"
        return "unknown"

    def normalize_driver_type(
        self,
        type_code: object,
        database_type: str | None = None,
    ) -> str:
        """Return a normalized field type for DB-API/PyMySQL cursor metadata."""
        label = str(database_type or "").strip().upper()
        if label.startswith("TYPE_") and type_code is not None:
            return "unknown"
        if label in self._DRIVER_TYPE_MAP:
            return self._DRIVER_TYPE_MAP[label]
        return self.normalize(label)
