"""Immutable UI-friendly result models for data management."""

from __future__ import annotations

from dataclasses import dataclass

from ..data_sources import DatasetField, QueryParameter, ReportDataset


@dataclass(frozen=True)
class DataManagementResult:
    """Safe result for simple management operations."""

    success: bool
    message: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class DataSourceSummary:
    """Credential-safe summary of a report data source."""

    id: str
    name: str
    type: str
    host: str | None
    port: int | None
    database: str | None
    username: str | None
    password_configured: bool
    password_ref_configured: bool


@dataclass(frozen=True)
class DatasetSummary:
    """Safe summary of a report dataset for UI listings."""

    id: str
    name: str
    data_source_id: str
    source_type: str
    source_label: str
    field_count: int
    parameter_count: int
    is_validated: bool | None = None


@dataclass(frozen=True)
class DatasetFieldChangeSummary:
    """Names added, removed, or type-changed by a field refresh."""

    added: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()
    changed: tuple[str, ...] = ()


@dataclass(frozen=True)
class DatasetConfigurationResult:
    """Detailed result for dataset create, update, discovery, or refresh operations."""

    dataset: ReportDataset
    fields: tuple[DatasetField, ...]
    parameters: tuple[QueryParameter, ...]
    warnings: tuple[str, ...] = ()
    changes: DatasetFieldChangeSummary | None = None
