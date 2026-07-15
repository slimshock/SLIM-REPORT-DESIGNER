"""Immutable limits for bounded dataset execution."""

from __future__ import annotations

from dataclasses import dataclass

from .errors import DatasetExecutionConfigurationError


@dataclass(frozen=True)
class DatasetExecutionPolicy:
    """Fail-closed limits shared by dataset executions."""

    max_rows: int = 10_000
    batch_size: int = 200
    max_columns: int = 500
    max_execution_timeout_seconds: int = 30
    max_cell_bytes: int = 1_048_576
    max_total_bytes: int = 67_108_864
    require_declared_fields: bool = True
    require_exact_field_schema: bool = True
    require_unique_column_names: bool = True
    allow_binary_values: bool = True
    allow_unknown_value_types: bool = False

    def __post_init__(self) -> None:
        for name in (
            "max_rows",
            "batch_size",
            "max_columns",
            "max_execution_timeout_seconds",
            "max_cell_bytes",
            "max_total_bytes",
        ):
            _positive_integer(getattr(self, name), name)
        for name in (
            "require_declared_fields",
            "require_exact_field_schema",
            "require_unique_column_names",
            "allow_binary_values",
            "allow_unknown_value_types",
        ):
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"{name} must be a boolean.")
        if self.batch_size > self.max_rows:
            raise ValueError("batch_size must not exceed max_rows.")
        if self.max_total_bytes < self.max_cell_bytes:
            raise ValueError("max_total_bytes must not be less than max_cell_bytes.")


@dataclass(frozen=True)
class DatasetExecutionOptions:
    """Optional stricter limits for one execution."""

    max_rows: int | None = None
    batch_size: int | None = None
    timeout_seconds: int | None = None

    def __post_init__(self) -> None:
        for name in ("max_rows", "batch_size", "timeout_seconds"):
            value = getattr(self, name)
            if value is not None:
                _positive_integer(value, name)


@dataclass(frozen=True)
class EffectiveDatasetExecutionConfiguration:
    """Internal immutable limits calculated for one stream."""

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


def effective_execution_configuration(
    policy: DatasetExecutionPolicy,
    options: DatasetExecutionOptions | None,
    *,
    data_source_timeout: int,
) -> EffectiveDatasetExecutionConfiguration:
    """Validate requested limits and return one execution configuration."""
    requested = options or DatasetExecutionOptions()
    _reject_above_policy("max_rows", requested.max_rows, policy.max_rows)
    _reject_above_policy("batch_size", requested.batch_size, policy.batch_size)
    _reject_above_policy(
        "timeout_seconds",
        requested.timeout_seconds,
        policy.max_execution_timeout_seconds,
    )
    max_rows = requested.max_rows or policy.max_rows
    batch_size = min(requested.batch_size or policy.batch_size, max_rows)
    timeout = min(
        requested.timeout_seconds or policy.max_execution_timeout_seconds,
        data_source_timeout,
        policy.max_execution_timeout_seconds,
    )
    return EffectiveDatasetExecutionConfiguration(
        max_rows=max_rows,
        batch_size=batch_size,
        timeout_seconds=timeout,
        max_columns=policy.max_columns,
        max_cell_bytes=policy.max_cell_bytes,
        max_total_bytes=policy.max_total_bytes,
        require_exact_field_schema=policy.require_exact_field_schema,
        require_unique_column_names=policy.require_unique_column_names,
        allow_binary_values=policy.allow_binary_values,
        allow_unknown_value_types=policy.allow_unknown_value_types,
    )


def _positive_integer(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer.")


def _reject_above_policy(name: str, requested: int | None, maximum: int) -> None:
    if requested is not None and requested > maximum:
        raise DatasetExecutionConfigurationError(
            f"{name} exceeds the configured execution limit of {maximum}."
        )
