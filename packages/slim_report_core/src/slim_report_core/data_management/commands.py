"""Immutable command models for data-source and dataset management."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..data_sources import QueryParameter


@dataclass(frozen=True)
class CreateMySQLDataSourceCommand:
    """Create a MySQL report data-source definition."""

    name: str
    host: str
    port: int
    database: str
    username: str
    password: str | None = field(default=None, repr=False)
    password_ref: str | None = None
    charset: str = "utf8mb4"
    connect_timeout: int = 10
    query_timeout: int = 30
    data_source_id: str | None = None


@dataclass(frozen=True)
class UpdateMySQLDataSourceCommand:
    """Atomically update an existing MySQL data-source definition."""

    data_source_id: str
    name: str | None = None
    host: str | None = None
    port: int | None = None
    database: str | None = None
    username: str | None = None
    runtime_password: str | None = field(default=None, repr=False)
    password_ref: str | None = None
    clear_runtime_password: bool = False
    clear_password_ref: bool = False
    charset: str | None = None
    connect_timeout: int | None = None
    query_timeout: int | None = None


@dataclass(frozen=True)
class CreateViewDatasetCommand:
    """Create a dataset backed by an approved database view."""

    name: str
    data_source_id: str
    view_name: str
    dataset_id: str | None = None
    discover_fields: bool = True


@dataclass(frozen=True)
class CreateQueryDatasetCommand:
    """Create a dataset backed by a custom validated SELECT query."""

    name: str
    data_source_id: str
    query: str
    parameters: tuple[QueryParameter, ...] = ()
    dataset_id: str | None = None
    discover_fields: bool = False
