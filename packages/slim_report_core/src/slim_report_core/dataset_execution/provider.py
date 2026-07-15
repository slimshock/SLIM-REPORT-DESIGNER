"""Internal provider execution capability and request contracts."""

from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Protocol, runtime_checkable

from ..data_sources import DatasetField, ReportDataSource
from .cancellation import DatasetExecutionCancellationToken
from .errors import DatasetExecutionProviderError


@dataclass(frozen=True)
class ProviderDatasetExecutionRequest:
    """Private execution snapshot passed to one provider stream."""

    dataset_id: str
    dataset_name: str
    data_source: ReportDataSource
    source_type: str
    sql: str
    parameters: Mapping[str, object]
    fields: tuple[DatasetField, ...]
    max_rows: int
    batch_size: int
    timeout_seconds: int
    max_columns: int
    max_cell_bytes: int
    max_total_bytes: int
    require_exact_field_schema: bool
    require_unique_column_names: bool
    allow_binary_values: bool
    allow_unknown_value_types: bool
    cancellation_token: DatasetExecutionCancellationToken | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "data_source", copy.deepcopy(self.data_source))
        object.__setattr__(self, "parameters", MappingProxyType(dict(self.parameters)))
        object.__setattr__(self, "fields", tuple(copy.deepcopy(self.fields)))


class ProviderDatasetRowStream(Protocol):
    """Private raw row source owned by a provider."""

    column_names: tuple[str, ...]

    def fetchmany(self, size: int) -> Sequence[object]:
        """Fetch at most one bounded batch from the driver."""
        ...

    def close(self) -> None:
        """Close cursor and connection idempotently."""
        ...


@runtime_checkable
class DatasetExecutionProvider(Protocol):
    """Narrow capability implemented by the MySQL provider."""

    provider_type: str

    def open_dataset_stream(
        self,
        request: ProviderDatasetExecutionRequest,
    ) -> ProviderDatasetRowStream:
        """Execute one prepared request and return a raw unbuffered stream."""
        ...


def require_dataset_execution_provider(provider: object) -> DatasetExecutionProvider:
    """Resolve execution capability at one central boundary."""
    if not isinstance(provider, DatasetExecutionProvider):
        provider_type = str(getattr(provider, "provider_type", "unknown"))
        raise DatasetExecutionProviderError(
            f"The provider '{provider_type}' does not support dataset execution."
        )
    return provider
