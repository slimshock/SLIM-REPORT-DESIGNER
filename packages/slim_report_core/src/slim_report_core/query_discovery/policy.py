"""Fail-closed policy for query field discovery."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QueryFieldDiscoveryPolicy:
    """Limits and behavior switches for metadata-only query discovery."""

    max_preview_rows: int = 1
    max_columns: int = 500
    max_query_length: int = 100_000
    max_parameters: int = 100
    require_unique_column_names: bool = True
    allow_duplicate_column_names: bool = False
    require_parameter_values: bool = True
    fail_on_unknown_types: bool = False
    execution_timeout_seconds: int = 15

    def __post_init__(self) -> None:
        for field_name in (
            "max_preview_rows",
            "max_columns",
            "max_query_length",
            "max_parameters",
            "execution_timeout_seconds",
        ):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{field_name} must be a positive integer.")
        for field_name in (
            "require_unique_column_names",
            "allow_duplicate_column_names",
            "require_parameter_values",
            "fail_on_unknown_types",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise ValueError(f"{field_name} must be a boolean.")
        if self.require_unique_column_names and self.allow_duplicate_column_names:
            raise ValueError(
                "allow_duplicate_column_names cannot be true when "
                "require_unique_column_names is true."
            )
