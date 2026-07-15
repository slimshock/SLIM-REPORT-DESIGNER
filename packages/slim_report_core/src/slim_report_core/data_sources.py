"""Framework-agnostic data-source metadata models."""

from __future__ import annotations

import copy
import math
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import Any, Protocol

from .exceptions import (
    CredentialResolutionError,
    DatasetValidationError,
    DataSourceValidationError,
)
from .utils import ensure_mapping

MYSQL_DATA_SOURCE_TYPE = "mysql"
SUPPORTED_FIELD_TYPES = {
    "binary",
    "boolean",
    "date",
    "datetime",
    "decimal",
    "float",
    "integer",
    "string",
    "time",
    "unknown",
}
SUPPORTED_PARAMETER_TYPES = {
    "boolean",
    "date",
    "datetime",
    "decimal",
    "float",
    "integer",
    "string",
    "time",
}

_SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SAFE_QUALIFIED_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?$")


class CredentialResolver(Protocol):
    """Resolve a credential reference to its runtime secret value."""

    def resolve(
        self,
        reference: str,
        *,
        data_source: ReportDataSource | None = None,
    ) -> str | None:
        """Return the resolved secret value, or None when not found."""
        ...


class EnvironmentCredentialResolver:
    """Resolve credential references from environment variables."""

    source_label = "environment"

    def resolve(
        self,
        reference: str,
        *,
        data_source: ReportDataSource | None = None,
    ) -> str | None:
        """Return the value of the named environment variable."""
        del data_source
        if not isinstance(reference, str) or not reference.strip() or "\x00" in reference:
            raise ValueError("Credential reference must be a non-empty environment key.")
        return os.getenv(reference.strip())


@dataclass
class MySQLConnectionConfig:
    """Serializable MySQL connection settings for report metadata.

    The runtime password is intentionally excluded from normal serialization.
    Store ``password_ref`` in report JSON and resolve it at runtime instead.
    """

    host: str = "localhost"
    port: int = 3306
    database: str = ""
    username: str = ""
    password: str | None = field(default=None, repr=False)
    password_ref: str | None = None
    charset: str = "utf8mb4"
    connect_timeout: int = 10
    query_timeout: int = 30

    def __post_init__(self) -> None:
        self.host = _required_text(self.host, "connection.host", DataSourceValidationError)
        self.port = _mysql_port(self.port)
        self.database = _required_text(
            self.database,
            "connection.database",
            DataSourceValidationError,
        )
        self.username = _required_text(
            self.username,
            "connection.username",
            DataSourceValidationError,
        )
        self.password = _optional_text(self.password)
        self.password_ref = _credential_reference(self.password_ref)
        self.charset = _required_text(
            self.charset,
            "connection.charset",
            DataSourceValidationError,
        )
        self.connect_timeout = _positive_mysql_timeout(
            self.connect_timeout,
            default=10,
            field_name="connection.connectTimeout",
        )
        self.query_timeout = _positive_mysql_timeout(
            self.query_timeout,
            default=30,
            field_name="connection.queryTimeout",
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> MySQLConnectionConfig:
        """Deserialize a MySQL connection config from JSON-compatible data."""
        mapping = ensure_mapping(data, context="MySQL connection")
        connection_type = mapping.get("type", MYSQL_DATA_SOURCE_TYPE)
        if str(connection_type) != MYSQL_DATA_SOURCE_TYPE:
            raise DataSourceValidationError(f"connection.type must be {MYSQL_DATA_SOURCE_TYPE!r}.")
        return cls(
            host=str(mapping.get("host") or "localhost"),
            port=mapping.get("port", 3306),
            database=str(mapping.get("database") or ""),
            username=str(mapping.get("username") or ""),
            password=_optional_text(mapping.get("password")),
            password_ref=_credential_reference(
                mapping.get("passwordRef", mapping.get("password_ref"))
            ),
            charset=str(mapping.get("charset", "utf8mb4") or "utf8mb4"),
            connect_timeout=mapping.get(
                "connectTimeout",
                mapping.get("connect_timeout", 10),
            ),
            query_timeout=mapping.get(
                "queryTimeout",
                mapping.get("query_timeout", 30),
            ),
        )

    def to_dict(self, *, include_password: bool = False) -> dict[str, Any]:
        """Serialize this config, excluding the runtime password by default."""
        data: dict[str, Any] = {
            "type": MYSQL_DATA_SOURCE_TYPE,
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "username": self.username,
            "charset": self.charset,
            "connectTimeout": self.connect_timeout,
            "queryTimeout": self.query_timeout,
        }
        if self.password_ref is not None:
            data["passwordRef"] = self.password_ref
        if include_password and self.password is not None:
            data["password"] = self.password
        return data

    def resolve_password(
        self,
        resolver: CredentialResolver | None = None,
    ) -> str | None:
        """Resolve a password without logging or serializing the resolved value."""
        if self.password is not None:
            return self.password
        if self.password_ref is None:
            return None

        if resolver is not None:
            try:
                try:
                    resolved = resolver.resolve(self.password_ref, data_source=None)
                except TypeError:
                    resolved = resolver.resolve(self.password_ref)
            except Exception as exc:  # pragma: no cover - defensive boundary
                raise CredentialResolutionError(
                    "Could not resolve the configured credential reference."
                ) from exc
            if resolved is not None:
                return resolved

        return EnvironmentCredentialResolver().resolve(self.password_ref)


def _credential_reference(value: Any) -> str | None:
    reference = _optional_text(value)
    if reference is None:
        return None
    if "\x00" in reference:
        raise DataSourceValidationError("connection.passwordRef must not contain null bytes.")
    return reference


@dataclass
class ReportDataSource:
    """A named report data source."""

    id: str = ""
    name: str = ""
    type: str = MYSQL_DATA_SOURCE_TYPE
    connection: MySQLConnectionConfig | Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        self.name = _required_text(self.name, "dataSource.name", DataSourceValidationError)
        self.id = _optional_text(self.id) or _make_stable_id("data_source", self.name)
        self.type = str(self.type or MYSQL_DATA_SOURCE_TYPE)
        if self.type != MYSQL_DATA_SOURCE_TYPE:
            raise DataSourceValidationError(f"Unsupported dataSource.type: {self.type}.")
        if self.connection is None:
            raise DataSourceValidationError(
                "dataSource.connection must be a MySQLConnectionConfig."
            )
        if isinstance(self.connection, Mapping):
            self.connection = MySQLConnectionConfig.from_dict(self.connection)
        if not isinstance(self.connection, MySQLConnectionConfig):
            raise DataSourceValidationError(
                "dataSource.connection must be a MySQLConnectionConfig."
            )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ReportDataSource:
        """Deserialize a report data source from JSON-compatible data."""
        mapping = ensure_mapping(data, context="Report data source")
        source_type = str(mapping.get("type", MYSQL_DATA_SOURCE_TYPE) or MYSQL_DATA_SOURCE_TYPE)
        connection_data = mapping.get("connection")
        if isinstance(connection_data, Mapping):
            connection = MySQLConnectionConfig.from_dict(
                {"type": source_type, **dict(connection_data)}
            )
        else:
            connection = MySQLConnectionConfig.from_dict(mapping)
        return cls(
            id=str(mapping.get("id") or ""),
            name=str(mapping.get("name") or ""),
            type=source_type,
            connection=connection,
        )

    def to_dict(self, *, include_password: bool = False) -> dict[str, Any]:
        """Serialize this data source with camelCase connection keys."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "connection": self.connection.to_dict(include_password=include_password),
        }


class DatasetSourceType(str, Enum):
    """Supported report dataset source types."""

    VIEW = "view"
    QUERY = "query"


@dataclass
class DatasetField:
    """Field metadata discovered or declared for a dataset."""

    name: str
    data_type: str = "string"
    nullable: bool = True
    label: str | None = None
    source_name: str | None = None

    def __post_init__(self) -> None:
        self.name = _required_text(self.name, "field.name", DatasetValidationError)
        self.data_type = _normalize_field_type(self.data_type)
        self.nullable = bool(self.nullable)
        self.label = _optional_text(self.label)
        self.source_name = _optional_text(self.source_name)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DatasetField:
        """Deserialize dataset field metadata."""
        mapping = ensure_mapping(data, context="Dataset field")
        return cls(
            name=str(mapping.get("name") or ""),
            data_type=str(mapping.get("dataType", mapping.get("data_type", "string"))),
            nullable=bool(mapping.get("nullable", True)),
            label=_optional_text(mapping.get("label")),
            source_name=_optional_text(mapping.get("sourceName", mapping.get("source_name"))),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize dataset field metadata."""
        data: dict[str, Any] = {
            "name": self.name,
            "dataType": self.data_type,
            "nullable": self.nullable,
        }
        if self.label is not None:
            data["label"] = self.label
        if self.source_name is not None:
            data["sourceName"] = self.source_name
        return data


@dataclass
class QueryParameter:
    """Parameterized query metadata.

    Parameter values are metadata only; this model never interpolates values
    into SQL strings.
    """

    name: str
    data_type: str = "string"
    required: bool = False
    default: Any = None
    label: str | None = None

    def __post_init__(self) -> None:
        self.name = _required_text(self.name, "parameter.name", DatasetValidationError)
        if _SAFE_IDENTIFIER_RE.fullmatch(self.name) is None:
            raise DatasetValidationError(f"parameter.name must be a safe identifier: {self.name}.")
        self.data_type = _normalize_parameter_type(self.data_type)
        self.required = bool(self.required)
        self.default = copy.deepcopy(self.default)
        query_parameter_default_to_json(self.default)
        self.label = _optional_text(self.label)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> QueryParameter:
        """Deserialize query parameter metadata."""
        mapping = ensure_mapping(data, context="Query parameter")
        return cls(
            name=str(mapping.get("name") or ""),
            data_type=str(mapping.get("dataType", mapping.get("data_type", "string"))),
            required=bool(mapping.get("required", False)),
            default=copy.deepcopy(mapping.get("default")),
            label=_optional_text(mapping.get("label")),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize query parameter metadata."""
        data: dict[str, Any] = {
            "name": self.name,
            "dataType": self.data_type,
            "required": self.required,
        }
        if self.default is not None:
            data["default"] = query_parameter_default_to_json(self.default)
        if self.label is not None:
            data["label"] = self.label
        return data


def query_parameter_default_to_json(value: Any) -> Any:
    """Return a deterministic JSON-safe query parameter default."""
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise DatasetValidationError("parameter.default must be a finite value.")
        return value
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise DatasetValidationError("parameter.default must be a finite value.")
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (date, time)):
        return value.isoformat()
    raise DatasetValidationError("parameter.default must be a supported scalar value.")


@dataclass
class ReportDataset:
    """A view- or SELECT-query-backed dataset declaration."""

    id: str = ""
    name: str = ""
    data_source_id: str = ""
    source_type: DatasetSourceType | str = DatasetSourceType.VIEW
    view_name: str | None = None
    query: str | None = None
    fields: list[DatasetField] = field(default_factory=list)
    parameters: list[QueryParameter] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.name = _required_text(self.name, "dataset.name", DatasetValidationError)
        self.id = _optional_text(self.id) or _make_stable_id("dataset", self.name)
        self.data_source_id = _required_text(
            self.data_source_id,
            "dataset.dataSourceId",
            DatasetValidationError,
        )
        self.source_type = _normalize_source_type(self.source_type)
        self.view_name = _optional_text(self.view_name)
        self.query = _optional_query(self.query)
        self.fields = [_normalize_field(item) for item in self.fields]
        self.parameters = [_normalize_parameter(item) for item in self.parameters]
        self._validate_source()
        _require_unique_names(
            [item.name for item in self.fields],
            "dataset.fields",
            DatasetValidationError,
        )
        _require_unique_names(
            [item.name for item in self.parameters],
            "dataset.parameters",
            DatasetValidationError,
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ReportDataset:
        """Deserialize a report dataset from JSON-compatible data."""
        mapping = ensure_mapping(data, context="Report dataset")
        return cls(
            id=str(mapping.get("id") or ""),
            name=str(mapping.get("name") or ""),
            data_source_id=str(mapping.get("dataSourceId", mapping.get("data_source_id")) or ""),
            source_type=str(mapping.get("sourceType", mapping.get("source_type", "view"))),
            view_name=_optional_text(mapping.get("viewName", mapping.get("view_name"))),
            query=_optional_text(mapping.get("query")),
            fields=[
                DatasetField.from_dict(item)
                for item in mapping.get("fields", [])
                if isinstance(item, Mapping)
            ],
            parameters=[
                QueryParameter.from_dict(item)
                for item in mapping.get("parameters", [])
                if isinstance(item, Mapping)
            ],
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize this dataset with camelCase relationship keys."""
        data: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "dataSourceId": self.data_source_id,
            "sourceType": self.source_type.value,
            "fields": [item.to_dict() for item in self.fields],
            "parameters": [item.to_dict() for item in self.parameters],
        }
        if self.source_type is DatasetSourceType.VIEW:
            data["viewName"] = self.view_name
        if self.source_type is DatasetSourceType.QUERY:
            data["query"] = self.query
        return data

    def _validate_source(self) -> None:
        if self.source_type is DatasetSourceType.VIEW:
            if self.view_name is None:
                raise DatasetValidationError("dataset.viewName is required for view datasets.")
            if _SAFE_QUALIFIED_IDENTIFIER_RE.fullmatch(self.view_name) is None:
                raise DatasetValidationError(
                    f"dataset.viewName must be a safe identifier: {self.view_name}."
                )
            self.query = None
            return

        if self.query is None:
            raise DatasetValidationError("dataset.query is required for query datasets.")
        self.view_name = None


def _normalize_field(value: DatasetField | Mapping[str, Any]) -> DatasetField:
    if isinstance(value, DatasetField):
        return value
    if isinstance(value, Mapping):
        return DatasetField.from_dict(value)
    raise DatasetValidationError("dataset.fields must contain DatasetField instances.")


def _normalize_parameter(value: QueryParameter | Mapping[str, Any]) -> QueryParameter:
    if isinstance(value, QueryParameter):
        return value
    if isinstance(value, Mapping):
        return QueryParameter.from_dict(value)
    raise DatasetValidationError("dataset.parameters must contain QueryParameter instances.")


def _normalize_source_type(value: DatasetSourceType | str) -> DatasetSourceType:
    if isinstance(value, DatasetSourceType):
        return value
    try:
        return DatasetSourceType(str(value))
    except ValueError as exc:
        raise DatasetValidationError(f"Unsupported dataset.sourceType: {value}.") from exc


def _normalize_field_type(value: str) -> str:
    normalized = str(value or "string").strip().lower()
    return normalized if normalized in SUPPORTED_FIELD_TYPES else "unknown"


def _normalize_parameter_type(value: str) -> str:
    normalized = str(value or "string").strip().lower()
    if normalized not in SUPPORTED_PARAMETER_TYPES:
        raise DatasetValidationError(f"Unsupported parameter.dataType: {value}.")
    return normalized


def _mysql_port(value: Any) -> int:
    if value is None:
        return 3306
    normalized = _strict_integer(value)
    if normalized is None or not 1 <= normalized <= 65535:
        raise DataSourceValidationError("connection.port must be an integer between 1 and 65535.")
    return normalized


def _positive_mysql_timeout(value: Any, *, default: int, field_name: str) -> int:
    if value is None:
        return default
    normalized = _strict_integer(value)
    if normalized is None or normalized < 1:
        raise DataSourceValidationError(f"{field_name} must be a positive integer.")
    return normalized


def _strict_integer(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip()
        if re.fullmatch(r"[+-]?\d+", text) is not None:
            try:
                return int(text)
            except (ValueError, OverflowError):
                return None
    return None


def _required_text(value: Any, field_name: str, error_type: type[Exception]) -> str:
    text = str(value or "").strip()
    if text == "":
        raise error_type(f"{field_name} must not be empty.")
    return text


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_query(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text.strip() else None


def _make_stable_id(prefix: str, name: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_]+", "_", name.strip().lower()).strip("_")
    return f"{prefix}_{normalized or 'item'}"


def _require_unique_names(
    names: list[str],
    context: str,
    error_type: type[Exception],
) -> None:
    seen: set[str] = set()
    for name in names:
        key = name.lower()
        if key in seen:
            raise error_type(f"{context} contains a duplicate name: {name}.")
        seen.add(key)
