"""Immutable public models for streamed dataset execution."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class DatasetExecutionField:
    """Driver-neutral field metadata for an execution stream."""

    name: str
    data_type: str
    nullable: bool
    ordinal_position: int
    source_name: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("Execution field name must not be empty.")
        if not isinstance(self.data_type, str) or not self.data_type:
            raise ValueError("Execution field type must not be empty.")
        if not isinstance(self.nullable, bool):
            raise ValueError("Execution field nullable must be boolean.")
        if (
            isinstance(self.ordinal_position, bool)
            or not isinstance(self.ordinal_position, int)
            or self.ordinal_position < 1
        ):
            raise ValueError("Execution field ordinal_position must be positive.")
        if self.source_name is not None and (
            not isinstance(self.source_name, str) or not self.source_name
        ):
            raise ValueError("Execution field source_name must be non-empty text.")


@dataclass(frozen=True)
class DatasetExecutionSchema:
    """Stored schema validated against the live cursor description."""

    dataset_id: str
    dataset_name: str
    fields: tuple[DatasetExecutionField, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "fields", tuple(self.fields))


@dataclass(frozen=True)
class DatasetRow:
    """One immutable, one-based dataset row."""

    index: int
    values: Mapping[str, object]

    def __post_init__(self) -> None:
        if isinstance(self.index, bool) or not isinstance(self.index, int) or self.index < 1:
            raise ValueError("Dataset row index must be a positive integer.")
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))

    def get(self, field_name: str, default: object = None) -> object:
        """Return one field value without changing the row."""
        return self.values.get(field_name, default)


@dataclass(frozen=True)
class DatasetRowBatch:
    """One bounded immutable batch of ordered rows."""

    start_index: int
    rows: tuple[DatasetRow, ...]

    def __post_init__(self) -> None:
        if (
            isinstance(self.start_index, bool)
            or not isinstance(self.start_index, int)
            or self.start_index < 1
        ):
            raise ValueError("Dataset batch start_index must be positive.")
        object.__setattr__(self, "rows", tuple(self.rows))


@dataclass(frozen=True)
class DatasetExecutionSummary:
    """Safe execution metadata that contains no SQL or values."""

    dataset_id: str
    dataset_name: str
    provider: str
    row_count: int
    field_count: int
    truncated: bool
    cancelled: bool
    elapsed_ms: float
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.row_count < 0 or self.field_count < 0:
            raise ValueError("Execution summary counts must not be negative.")
        if self.elapsed_ms < 0:
            raise ValueError("Execution summary elapsed_ms must not be negative.")
        object.__setattr__(self, "warnings", tuple(self.warnings))
