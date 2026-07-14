"""Immutable result models for safe query field discovery."""

from __future__ import annotations

from dataclasses import dataclass

from ..data_sources import DatasetField


@dataclass(frozen=True)
class DiscoveredColumn:
    """Driver-neutral metadata for one discovered query output column."""

    name: str
    ordinal_position: int
    database_type: str
    normalized_type: str
    nullable: bool | None = None
    precision: int | None = None
    scale: int | None = None
    length: int | None = None
    source_name: str | None = None


@dataclass(frozen=True)
class ProviderFieldDiscoveryResult:
    """Internal provider result without public cursor or connection objects."""

    columns: tuple[DiscoveredColumn, ...]
    sample_row_count: int
    elapsed_ms: float
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class QueryFieldDiscoveryResult:
    """Safe public result of field discovery for a query-backed dataset."""

    dataset_id: str
    dataset_name: str
    provider: str
    dialect: str
    fields: tuple[DatasetField, ...]
    parameters: tuple[str, ...]
    sample_row_count: int
    elapsed_ms: float
    warnings: tuple[str, ...] = ()
