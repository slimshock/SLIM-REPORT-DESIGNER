"""Framework-independent dataset execution preparation and orchestration."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import replace
from time import monotonic

from ..data_source_providers import (
    DataSourceProviderRegistry,
    InvalidViewIdentifierError,
    MetadataAccessDeniedError,
    MetadataAccessPolicy,
    MySQLMetadataService,
    UnsupportedDataSourceProviderError,
)
from ..data_source_providers.mysql.execution import build_mysql_view_select
from ..data_sources import (
    MYSQL_DATA_SOURCE_TYPE,
    SUPPORTED_FIELD_TYPES,
    DatasetSourceType,
    MySQLConnectionConfig,
    ReportDataset,
    ReportDataSource,
)
from ..report import Report
from ..runtime_parameters import RuntimeParameterResolver
from ..sql import SQLValidator
from .cancellation import DatasetExecutionCancellationToken
from .errors import (
    DatasetExecutionCancelledError,
    DatasetExecutionConfigurationError,
    DatasetExecutionProviderError,
    DatasetNotExecutableError,
    DatasetSchemaMismatchError,
)
from .models import DatasetExecutionField, DatasetExecutionSchema
from .policy import (
    DatasetExecutionOptions,
    DatasetExecutionPolicy,
    EffectiveDatasetExecutionConfiguration,
    effective_execution_configuration,
)
from .provider import (
    ProviderDatasetExecutionRequest,
    require_dataset_execution_provider,
)
from .stream import DatasetRowStream

logger = logging.getLogger(__name__)


class DatasetExecutionService:
    """Prepare and open bounded read-only MySQL dataset streams."""

    def __init__(
        self,
        *,
        provider_registry: DataSourceProviderRegistry,
        sql_validator: SQLValidator,
        parameter_resolver: RuntimeParameterResolver,
        policy: DatasetExecutionPolicy | None = None,
        metadata_policy: MetadataAccessPolicy | None = None,
    ) -> None:
        self.provider_registry = provider_registry
        self.sql_validator = sql_validator
        self.parameter_resolver = parameter_resolver
        self.policy = policy or DatasetExecutionPolicy()
        self.metadata_policy = metadata_policy or MetadataAccessPolicy()
        if getattr(self.sql_validator.dialect, "name", None) != MYSQL_DATA_SOURCE_TYPE:
            raise DatasetExecutionConfigurationError(
                "Dataset execution requires the MySQL SQL validator."
            )

    def open_dataset(
        self,
        report: Report,
        dataset_id: str,
        *,
        parameter_values: Mapping[str, object] | None = None,
        options: DatasetExecutionOptions | None = None,
        cancellation_token: DatasetExecutionCancellationToken | None = None,
    ) -> DatasetRowStream:
        """Validate all metadata before opening one provider-owned stream."""
        started = monotonic()
        if not isinstance(report, Report):
            raise DatasetNotExecutableError("Dataset execution requires a Report instance.")
        if not isinstance(dataset_id, str) or not dataset_id:
            raise DatasetNotExecutableError("A dataset ID is required for execution.")
        dataset = report.get_dataset(dataset_id)
        if dataset is None:
            raise DatasetNotExecutableError(f"Report dataset '{dataset_id}' was not found.")
        data_source = report.get_data_source(dataset.data_source_id)
        if data_source is None:
            raise DatasetNotExecutableError("The dataset's configured data source was not found.")
        if data_source.type != MYSQL_DATA_SOURCE_TYPE:
            raise DatasetExecutionProviderError(
                "Dataset execution currently requires a MySQL data source."
            )
        if dataset.data_source_id != data_source.id:
            raise DatasetNotExecutableError("The dataset and data source relationship is invalid.")
        try:
            provider = self.provider_registry.get(data_source.type)
        except UnsupportedDataSourceProviderError as exc:
            raise DatasetExecutionProviderError(
                "The configured data-source provider is not available."
            ) from exc
        execution_provider = require_dataset_execution_provider(provider)
        schema = self._execution_schema(dataset)
        configuration = self._configuration(data_source, options)
        self._check_cancelled(cancellation_token)

        parameters: dict[str, object] = {}
        if dataset.source_type is DatasetSourceType.QUERY:
            validation = self.sql_validator.validate_dataset(dataset)
            resolved = self.parameter_resolver.resolve_dataset(
                dataset,
                parameter_values,
            )
            sql = validation.normalized_sql
            parameters = dict(resolved.values)
        elif dataset.source_type is DatasetSourceType.VIEW:
            if dataset.parameters:
                raise DatasetNotExecutableError(
                    "View datasets cannot define runtime query parameters."
                )
            if parameter_values:
                raise DatasetNotExecutableError(
                    "View datasets do not accept runtime query parameters."
                )
            sql = self._view_sql(provider, data_source, dataset)
        else:  # pragma: no cover - model validation prevents this state
            raise DatasetNotExecutableError("The dataset type cannot be executed.")

        snapshot = self._data_source_snapshot(data_source, configuration.timeout_seconds)
        request = ProviderDatasetExecutionRequest(
            dataset_id=dataset.id,
            dataset_name=dataset.name,
            data_source=snapshot,
            source_type=dataset.source_type.value,
            sql=sql,
            parameters=parameters,
            fields=tuple(dataset.fields),
            max_rows=configuration.max_rows,
            batch_size=configuration.batch_size,
            timeout_seconds=configuration.timeout_seconds,
            max_columns=configuration.max_columns,
            max_cell_bytes=configuration.max_cell_bytes,
            max_total_bytes=configuration.max_total_bytes,
            require_exact_field_schema=configuration.require_exact_field_schema,
            require_unique_column_names=configuration.require_unique_column_names,
            allow_binary_values=configuration.allow_binary_values,
            allow_unknown_value_types=configuration.allow_unknown_value_types,
            cancellation_token=cancellation_token,
        )
        self._check_cancelled(cancellation_token)
        logger.info(
            "Dataset execution started for dataset %s using mysql: rows=%d, batch=%d, "
            "timeout=%d, fields=%d.",
            dataset.id,
            configuration.max_rows,
            configuration.batch_size,
            configuration.timeout_seconds,
            len(schema.fields),
        )
        raw_stream = execution_provider.open_dataset_stream(request)
        try:
            returned_names = tuple(raw_stream.column_names)
            self._validate_returned_schema(schema, returned_names, configuration)
        except Exception:
            raw_stream.close()
            raise
        return DatasetRowStream(
            raw_stream=raw_stream,
            schema=schema,
            returned_column_names=returned_names,
            provider=data_source.type,
            configuration=configuration,
            cancellation_token=cancellation_token,
            started=started,
        )

    def resolve_primary_dataset(
        self,
        report: Report,
        dataset_id: str | None = None,
    ) -> ReportDataset:
        """Resolve an explicit, Detail-band, or sole report dataset."""
        if not isinstance(report, Report):
            raise DatasetNotExecutableError("Dataset execution requires a Report instance.")
        if dataset_id is not None:
            dataset = report.get_dataset(dataset_id)
            if dataset is None:
                raise DatasetNotExecutableError(f"Report dataset '{dataset_id}' was not found.")
            return dataset
        detail_ids = {
            band.dataset_id
            for band in report.bands
            if band.dataset_id is not None
            and (band.id.casefold() == "detail" or band.type.casefold() == "detail")
        }
        if len(detail_ids) == 1:
            detail_id = next(iter(detail_ids))
            dataset = report.get_dataset(detail_id)
            if dataset is None:
                raise DatasetNotExecutableError(
                    "The Detail band references a missing report dataset."
                )
            return dataset
        if len(detail_ids) > 1:
            raise DatasetNotExecutableError("Select the dataset to use for report execution.")
        if len(report.datasets) == 1:
            return report.datasets[0]
        raise DatasetNotExecutableError("Select the dataset to use for report execution.")

    def _execution_schema(self, dataset: object) -> DatasetExecutionSchema:
        fields = tuple(getattr(dataset, "fields", ()))
        if self.policy.require_declared_fields and not fields:
            raise DatasetNotExecutableError(
                "The dataset has no discovered fields and cannot be executed."
            )
        if len(fields) > self.policy.max_columns:
            raise DatasetNotExecutableError(
                f"Dataset contains {len(fields)} fields, exceeding the execution limit of "
                f"{self.policy.max_columns}."
            )
        seen: set[str] = set()
        execution_fields: list[DatasetExecutionField] = []
        for ordinal, field in enumerate(fields, start=1):
            name = getattr(field, "name", None)
            if not isinstance(name, str) or not name:
                raise DatasetNotExecutableError("Dataset contains an invalid field name.")
            normalized = name.casefold()
            if normalized in seen:
                raise DatasetNotExecutableError(f"Dataset fields contain duplicate name '{name}'.")
            seen.add(normalized)
            data_type = getattr(field, "data_type", None)
            if not isinstance(data_type, str) or data_type not in SUPPORTED_FIELD_TYPES:
                raise DatasetNotExecutableError(
                    f"Dataset field '{name}' has an unsupported stored type."
                )
            nullable = getattr(field, "nullable", None)
            if not isinstance(nullable, bool):
                raise DatasetNotExecutableError(
                    f"Dataset field '{name}' has invalid nullable metadata."
                )
            source_name = getattr(field, "source_name", None)
            if source_name is not None and (not isinstance(source_name, str) or not source_name):
                raise DatasetNotExecutableError(
                    f"Dataset field '{name}' has invalid source-name metadata."
                )
            execution_fields.append(
                DatasetExecutionField(
                    name=name,
                    data_type=data_type,
                    nullable=nullable,
                    ordinal_position=ordinal,
                    source_name=source_name,
                )
            )
        return DatasetExecutionSchema(
            dataset_id=str(getattr(dataset, "id", "")),
            dataset_name=str(getattr(dataset, "name", "")),
            fields=tuple(execution_fields),
        )

    def _configuration(
        self,
        data_source: ReportDataSource,
        options: DatasetExecutionOptions | None,
    ) -> EffectiveDatasetExecutionConfiguration:
        config = data_source.connection
        if not isinstance(config, MySQLConnectionConfig):
            raise DatasetNotExecutableError(
                "The MySQL data source has an invalid connection configuration."
            )
        return effective_execution_configuration(
            self.policy,
            options,
            data_source_timeout=config.query_timeout,
        )

    def _view_sql(self, provider: object, data_source: ReportDataSource, dataset: object) -> str:
        view_name = getattr(dataset, "view_name", None)
        if not isinstance(view_name, str) or not view_name:
            raise DatasetNotExecutableError(
                "The configured reporting view is not available for execution."
            )
        try:
            schema_name, resolved_view = MySQLMetadataService(
                provider,  # type: ignore[arg-type]
                self.metadata_policy,
            ).resolve_view_identifier(data_source, view_name)
        except (InvalidViewIdentifierError, MetadataAccessDeniedError) as exc:
            raise DatasetNotExecutableError(
                "The configured reporting view is not available for execution."
            ) from exc
        return build_mysql_view_select(schema_name, resolved_view, dataset.fields)

    @staticmethod
    def _data_source_snapshot(
        data_source: ReportDataSource,
        timeout_seconds: int,
    ) -> ReportDataSource:
        config = data_source.connection
        if not isinstance(config, MySQLConnectionConfig):
            return data_source
        return ReportDataSource(
            id=data_source.id,
            name=data_source.name,
            type=data_source.type,
            connection=replace(config, query_timeout=timeout_seconds),
        )

    @staticmethod
    def _validate_returned_schema(
        schema: DatasetExecutionSchema,
        returned_names: tuple[str, ...],
        configuration: EffectiveDatasetExecutionConfiguration,
    ) -> None:
        if not returned_names:
            raise DatasetSchemaMismatchError("The dataset query did not return any columns.")
        if len(returned_names) > configuration.max_columns:
            raise DatasetSchemaMismatchError(
                "The dataset query returned more columns than the execution limit."
            )
        normalized = [name.casefold() for name in returned_names]
        if configuration.require_unique_column_names and len(set(normalized)) != len(normalized):
            raise DatasetSchemaMismatchError("The dataset query returned duplicate column names.")
        expected = tuple(field.name.casefold() for field in schema.fields)
        if len(expected) != len(normalized):
            raise DatasetSchemaMismatchError(
                "The query result no longer matches the stored dataset fields. "
                "Refresh or rediscover the dataset fields before running the report."
            )
        if configuration.require_exact_field_schema and expected != tuple(normalized):
            raise DatasetSchemaMismatchError(
                "The query result no longer matches the stored dataset fields. "
                "Refresh or rediscover the dataset fields before running the report."
            )

    @staticmethod
    def _check_cancelled(token: DatasetExecutionCancellationToken | None) -> None:
        if token is not None and token.is_cancelled:
            raise DatasetExecutionCancelledError("Dataset execution was cancelled.")
