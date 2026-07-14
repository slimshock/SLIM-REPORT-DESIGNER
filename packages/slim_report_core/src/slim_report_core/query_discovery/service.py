"""Generic safe query field discovery orchestration."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Protocol

from ..data_source_providers.errors import UnsupportedDataSourceProviderError
from ..data_source_providers.registry import DataSourceProviderRegistry
from ..data_sources import (
    DatasetField,
    DatasetSourceType,
    QueryParameter,
    ReportDataset,
    ReportDataSource,
)
from ..sql import SQLValidationError, SQLValidator
from .errors import (
    DuplicateOutputColumnError,
    QueryFieldDiscoveryError,
    QueryParameterError,
    QueryReturnedNoColumnsError,
    QueryValidationFailedError,
    TooManyOutputColumnsError,
    UnsupportedDiscoveredTypeError,
)
from .models import ProviderFieldDiscoveryResult, QueryFieldDiscoveryResult
from .parameters import QueryParameterValueConverter, missing_parameter_value
from .policy import QueryFieldDiscoveryPolicy

logger = logging.getLogger(__name__)


class QueryFieldDiscoveryProvider(Protocol):
    """Focused provider capability for SQL query field discovery."""

    provider_type: str
    dialect_name: str

    def discover_query_fields(
        self,
        *,
        data_source: ReportDataSource,
        sql: str,
        parameters: Mapping[str, object],
        policy: QueryFieldDiscoveryPolicy,
    ) -> ProviderFieldDiscoveryResult:
        """Execute metadata-limited discovery for one validated query."""
        ...


class QueryFieldDiscoveryService:
    """Validate query datasets and delegate metadata-only execution to providers."""

    def __init__(
        self,
        provider_registry: DataSourceProviderRegistry,
        sql_validator: SQLValidator,
        policy: QueryFieldDiscoveryPolicy | None = None,
        parameter_converter: QueryParameterValueConverter | None = None,
    ) -> None:
        self.provider_registry = provider_registry
        self.sql_validator = sql_validator
        self.policy = policy or QueryFieldDiscoveryPolicy()
        self.parameter_converter = parameter_converter or QueryParameterValueConverter()

    def discover_fields(
        self,
        *,
        dataset: ReportDataset,
        data_source: ReportDataSource,
        parameter_values: Mapping[str, object] | None = None,
    ) -> QueryFieldDiscoveryResult:
        """Discover query output fields without mutating the dataset."""
        self._validate_dataset_source(dataset, data_source)
        self._validate_discovery_policy_against_sql_policy()

        try:
            validation = self.sql_validator.validate_dataset(dataset)
        except SQLValidationError as exc:
            raise QueryValidationFailedError(str(exc)) from exc

        declared = {parameter.name: parameter for parameter in dataset.parameters}
        converted = self._resolve_parameter_values(
            declared=declared,
            referenced=validation.parameters,
            parameter_values=parameter_values or {},
        )
        provider = self._discovery_provider(data_source.type)
        logger.info(
            "Query field discovery started for dataset %s using provider %s.",
            dataset.id,
            provider.provider_type,
        )
        provider_result = provider.discover_query_fields(
            data_source=data_source,
            sql=validation.normalized_sql,
            parameters=converted,
            policy=self.policy,
        )
        fields = self._fields_from_provider_result(provider_result)
        warnings = validation.warnings + provider_result.warnings
        logger.info(
            "Query field discovery returned %d columns for dataset %s in %.3f ms.",
            len(fields),
            dataset.id,
            provider_result.elapsed_ms,
        )
        return QueryFieldDiscoveryResult(
            dataset_id=dataset.id,
            dataset_name=dataset.name,
            provider=provider.provider_type,
            dialect=validation.dialect,
            fields=fields,
            parameters=validation.parameters,
            sample_row_count=provider_result.sample_row_count,
            elapsed_ms=provider_result.elapsed_ms,
            warnings=warnings,
        )

    def apply_fields(
        self,
        dataset: ReportDataset,
        result: QueryFieldDiscoveryResult,
    ) -> ReportDataset:
        """Return a dataset copy with discovered fields applied explicitly."""
        if dataset.id != result.dataset_id:
            raise QueryFieldDiscoveryError(
                "Discovered fields can only be applied to the source dataset."
            )
        return ReportDataset(
            id=dataset.id,
            name=dataset.name,
            data_source_id=dataset.data_source_id,
            source_type=dataset.source_type,
            view_name=dataset.view_name,
            query=dataset.query,
            fields=list(result.fields),
            parameters=list(dataset.parameters),
        )

    def _resolve_parameter_values(
        self,
        *,
        declared: Mapping[str, QueryParameter],
        referenced: tuple[str, ...],
        parameter_values: Mapping[str, object],
    ) -> dict[str, object]:
        unknown = [name for name in parameter_values if name not in declared]
        if unknown:
            raise QueryParameterError(
                f"Discovery values were provided for unknown query parameter ':{unknown[0]}'."
            )

        converted: dict[str, object] = {}
        for name in referenced:
            parameter = declared[name]
            raw_value = parameter_values.get(name, missing_parameter_value())
            converted[name] = self.parameter_converter.convert(
                parameter=parameter,
                value=raw_value,
            )
        return converted

    def _fields_from_provider_result(
        self,
        provider_result: ProviderFieldDiscoveryResult,
    ) -> tuple[DatasetField, ...]:
        columns = provider_result.columns
        if not columns:
            raise QueryReturnedNoColumnsError("The query did not return any columns.")
        if len(columns) > self.policy.max_columns:
            raise TooManyOutputColumnsError(
                f"The query returned {len(columns)} columns, exceeding the configured "
                f"maximum of {self.policy.max_columns}."
            )

        seen: set[str] = set()
        fields: list[DatasetField] = []
        for column in columns:
            if not column.name:
                raise QueryReturnedNoColumnsError(
                    "The query returned a column without a usable output name."
                )
            key = column.name.casefold()
            if self.policy.require_unique_column_names and key in seen:
                raise DuplicateOutputColumnError(
                    f"The query returned duplicate output column {column.name!r}. "
                    "Use explicit SQL aliases to make every output column unique."
                )
            seen.add(key)
            if column.normalized_type == "unknown" and self.policy.fail_on_unknown_types:
                raise UnsupportedDiscoveredTypeError(
                    f"The query returned unsupported database type {column.database_type!r}."
                )
            fields.append(
                DatasetField(
                    name=column.name,
                    data_type=column.normalized_type,
                    nullable=column.nullable if column.nullable is not None else True,
                    source_name=column.source_name,
                )
            )
        return tuple(fields)

    def _discovery_provider(self, provider_type: str) -> QueryFieldDiscoveryProvider:
        provider = self.provider_registry.get(provider_type)
        if not callable(getattr(provider, "discover_query_fields", None)):
            normalized = str(provider_type).strip().lower()
            raise UnsupportedDataSourceProviderError(
                f"The provider {normalized!r} does not support SQL query field discovery."
            )
        return provider  # type: ignore[return-value]

    def _validate_dataset_source(
        self,
        dataset: ReportDataset,
        data_source: ReportDataSource,
    ) -> None:
        if dataset.source_type is not DatasetSourceType.QUERY:
            raise QueryValidationFailedError("Query field discovery requires a query dataset.")
        if dataset.data_source_id != data_source.id:
            raise QueryValidationFailedError(
                "The dataset data source does not match the supplied data source."
            )

    def _validate_discovery_policy_against_sql_policy(self) -> None:
        sql_policy = getattr(self.sql_validator, "policy", None)
        if sql_policy is None:
            return
        if self.policy.max_query_length > sql_policy.max_query_length:
            raise QueryValidationFailedError(
                "The discovery query length policy cannot exceed the SQL validator policy."
            )
        if self.policy.max_parameters > sql_policy.max_parameters:
            raise QueryValidationFailedError(
                "The discovery parameter policy cannot exceed the SQL validator policy."
            )
