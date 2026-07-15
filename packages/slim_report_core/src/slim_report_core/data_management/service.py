"""Application-facing data-source and dataset management service."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from ..bindings import ReportBindingService
from ..data_source_providers import (
    ConnectionTestResult,
    DatabaseColumnInfo,
    DatabaseViewInfo,
    DatabaseViewSchema,
    DataSourceProviderRegistry,
    MetadataAccessPolicy,
    MySQLMetadataService,
)
from ..data_source_providers.errors import UnsupportedDataSourceProviderError
from ..data_sources import (
    MYSQL_DATA_SOURCE_TYPE,
    CredentialResolver,
    DatasetField,
    DatasetSourceType,
    MySQLConnectionConfig,
    QueryParameter,
    ReportDataset,
    ReportDataSource,
)
from ..query_discovery import QueryFieldDiscoveryResult, QueryFieldDiscoveryService
from ..report import Report
from ..sql import InvalidSQLParameterError, SQLValidationResult, SQLValidator
from .commands import (
    CreateMySQLDataSourceCommand,
    CreateQueryDatasetCommand,
    CreateViewDatasetCommand,
    UpdateMySQLDataSourceCommand,
)
from .errors import (
    DataManagementValidationError,
    DatasetInUseError,
    DatasetNotFoundError,
    DatasetTypeMismatchError,
    DataSourceInUseError,
    DataSourceNotFoundError,
    InvalidDatasetOperationError,
    StaleDiscoveryResultError,
)
from .results import (
    DataManagementResult,
    DatasetConfigurationResult,
    DatasetFieldChangeSummary,
    DatasetSummary,
    DataSourceSummary,
)


class DataSourceManagementService:
    """Coordinate report data sources, datasets, validators, and providers."""

    def __init__(
        self,
        *,
        provider_registry: DataSourceProviderRegistry,
        sql_validator: SQLValidator,
        query_discovery_service: QueryFieldDiscoveryService,
        credential_resolver: CredentialResolver | None = None,
    ) -> None:
        self.provider_registry = provider_registry
        self.sql_validator = sql_validator
        self.query_discovery_service = query_discovery_service
        self.credential_resolver = credential_resolver

    def list_data_sources(self, report: Report) -> tuple[DataSourceSummary, ...]:
        """Return data-source summaries in report order without exposing credentials."""
        return tuple(self._data_source_summary(item) for item in report.data_sources)

    def get_data_source(self, report: Report, data_source_id: str) -> ReportDataSource:
        """Return one report data source or raise a UI-suitable error."""
        data_source = report.get_data_source(data_source_id)
        if data_source is None:
            raise DataSourceNotFoundError(f"The data source {data_source_id!r} was not found.")
        return data_source

    def create_mysql_data_source(
        self,
        report: Report,
        command: CreateMySQLDataSourceCommand,
    ) -> ReportDataSource:
        """Create and add a MySQL data source without testing the connection."""
        data_source = self._data_source_from_create_command(command)
        if report.get_data_source(data_source.id) is not None:
            raise DataManagementValidationError(
                f"The data source {data_source.id!r} already exists."
            )
        return report.add_data_source(data_source)

    def update_mysql_data_source(
        self,
        report: Report,
        command: UpdateMySQLDataSourceCommand,
    ) -> ReportDataSource:
        """Replace one MySQL data source atomically after validating the proposed model."""
        current, index = self._find_data_source(report, command.data_source_id)
        if current.type != MYSQL_DATA_SOURCE_TYPE:
            raise DataManagementValidationError(
                f"The data source {current.id!r} is not a MySQL data source."
            )
        config = current.connection
        if not isinstance(config, MySQLConnectionConfig):
            raise DataManagementValidationError("The data source connection is invalid.")

        password = config.password
        password_ref = config.password_ref
        if command.clear_runtime_password:
            password = None
        if command.runtime_password is not None:
            password = command.runtime_password
        if command.clear_password_ref:
            password_ref = None
        if command.password_ref is not None:
            password_ref = command.password_ref

        replacement = ReportDataSource(
            id=current.id,
            name=command.name if command.name is not None else current.name,
            type=current.type,
            connection=MySQLConnectionConfig(
                host=command.host if command.host is not None else config.host,
                port=command.port if command.port is not None else config.port,
                database=command.database if command.database is not None else config.database,
                username=command.username if command.username is not None else config.username,
                password=password,
                password_ref=password_ref,
                charset=command.charset if command.charset is not None else config.charset,
                connect_timeout=(
                    command.connect_timeout
                    if command.connect_timeout is not None
                    else config.connect_timeout
                ),
                query_timeout=(
                    command.query_timeout
                    if command.query_timeout is not None
                    else config.query_timeout
                ),
            ),
        )
        self._replace_data_source(report, index, replacement)
        return replacement

    def test_data_source_connection(
        self,
        report: Report,
        data_source_id: str,
    ) -> ConnectionTestResult:
        """Test an existing report data source without mutating the report."""
        data_source = self.get_data_source(report, data_source_id)
        return self.provider_registry.get(data_source.type).test_connection(data_source)

    def test_mysql_configuration(
        self,
        command: CreateMySQLDataSourceCommand,
    ) -> ConnectionTestResult:
        """Test an unsaved MySQL configuration without adding it to a report."""
        data_source = self._data_source_from_create_command(command)
        return self.provider_registry.get(data_source.type).test_connection(data_source)

    def remove_data_source(
        self,
        report: Report,
        data_source_id: str,
        *,
        cascade: bool = False,
    ) -> DataManagementResult:
        """Remove a data source, rejecting dependent datasets unless cascade is explicit."""
        self.get_data_source(report, data_source_id)
        dependents = [item for item in report.datasets if item.data_source_id == data_source_id]
        if dependents and not cascade:
            raise DataSourceInUseError(
                f"The data source {data_source_id!r} is used by {len(dependents)} datasets "
                "and cannot be removed without cascade confirmation."
            )
        if cascade:
            for dataset in dependents:
                self._assert_dataset_not_referenced(report, dataset.id)
        report.remove_data_source(data_source_id, cascade=cascade)
        return DataManagementResult(
            success=True,
            message=f"Removed data source {data_source_id!r}.",
            warnings=(
                (f"Removed {len(dependents)} dependent datasets.",)
                if dependents and cascade
                else ()
            ),
        )

    def list_datasets(self, report: Report) -> tuple[DatasetSummary, ...]:
        """Return safe dataset summaries in report order."""
        return tuple(self._dataset_summary(item) for item in report.datasets)

    def get_dataset(self, report: Report, dataset_id: str) -> ReportDataset:
        """Return one report dataset or raise a UI-suitable error."""
        dataset = report.get_dataset(dataset_id)
        if dataset is None:
            raise DatasetNotFoundError(f"The dataset {dataset_id!r} was not found.")
        return dataset

    def list_available_views(
        self,
        report: Report,
        data_source_id: str,
        *,
        policy: MetadataAccessPolicy | None = None,
    ) -> tuple[DatabaseViewInfo, ...]:
        """List approved reporting views through the provider metadata service."""
        data_source = self.get_data_source(report, data_source_id)
        metadata = self._metadata_service(data_source, policy)
        return metadata.list_views(data_source)

    def inspect_view(
        self,
        report: Report,
        data_source_id: str,
        view_name: str,
        *,
        policy: MetadataAccessPolicy | None = None,
    ) -> DatabaseViewSchema:
        """Inspect an approved reporting view without creating a dataset."""
        data_source = self.get_data_source(report, data_source_id)
        metadata = self._metadata_service(data_source, policy)
        return metadata.inspect_view(data_source, view_name)

    def create_view_dataset(
        self,
        report: Report,
        command: CreateViewDatasetCommand,
        *,
        metadata_policy: MetadataAccessPolicy | None = None,
    ) -> DatasetConfigurationResult:
        """Create a view-backed dataset, optionally discovering fields first."""
        data_source = self.get_data_source(report, command.data_source_id)
        proposed = ReportDataset(
            id=command.dataset_id or "",
            name=command.name,
            data_source_id=command.data_source_id,
            source_type=DatasetSourceType.VIEW,
            view_name=command.view_name,
        )
        self._ensure_dataset_can_be_added(report, proposed)
        fields: tuple[DatasetField, ...] = ()
        warnings: tuple[str, ...] = ()
        if command.discover_fields:
            schema = self._metadata_service(data_source, metadata_policy).inspect_view(
                data_source,
                command.view_name,
            )
            fields, warnings = self._fields_from_columns(schema.columns)
            proposed = self._copy_dataset(proposed, fields=list(fields))

        dataset = report.add_dataset(proposed)
        return DatasetConfigurationResult(
            dataset=dataset,
            fields=tuple(dataset.fields),
            parameters=tuple(dataset.parameters),
            warnings=warnings,
        )

    def refresh_view_dataset_fields(
        self,
        report: Report,
        dataset_id: str,
        *,
        metadata_policy: MetadataAccessPolicy | None = None,
    ) -> DatasetConfigurationResult:
        """Reinspect a view dataset and atomically replace its fields."""
        dataset, index = self._find_dataset(report, dataset_id)
        self._require_dataset_type(dataset, DatasetSourceType.VIEW)
        data_source = self.get_data_source(report, dataset.data_source_id)
        schema = self._metadata_service(data_source, metadata_policy).inspect_view(
            data_source,
            dataset.view_name or "",
        )
        fields, warnings = self._fields_from_columns(schema.columns)
        replacement = self._copy_dataset(dataset, fields=list(fields))
        changes = self._field_changes(dataset.fields, replacement.fields)
        warnings += self._binding_change_warnings(
            report, dataset.id, dataset.fields, replacement.fields
        )
        self._replace_dataset(report, index, replacement)
        return DatasetConfigurationResult(
            dataset=replacement,
            fields=tuple(replacement.fields),
            parameters=tuple(replacement.parameters),
            warnings=warnings,
            changes=changes,
        )

    def inspect_view_dataset_fields(
        self,
        report: Report,
        dataset_id: str,
        *,
        metadata_policy: MetadataAccessPolicy | None = None,
    ) -> DatasetConfigurationResult:
        """Discover current view fields without changing the report."""
        dataset = self.get_dataset(report, dataset_id)
        self._require_dataset_type(dataset, DatasetSourceType.VIEW)
        data_source = self.get_data_source(report, dataset.data_source_id)
        schema = self._metadata_service(data_source, metadata_policy).inspect_view(
            data_source,
            dataset.view_name or "",
        )
        fields, warnings = self._fields_from_columns(schema.columns)
        return DatasetConfigurationResult(
            dataset=dataset,
            fields=fields,
            parameters=tuple(dataset.parameters),
            warnings=warnings,
            changes=self._field_changes(dataset.fields, list(fields)),
        )

    def create_query_dataset(
        self,
        report: Report,
        command: CreateQueryDatasetCommand,
        *,
        parameter_values: Mapping[str, object] | None = None,
    ) -> DatasetConfigurationResult:
        """Create a query-backed dataset after validation and optional discovery."""
        self.get_data_source(report, command.data_source_id)
        proposed = ReportDataset(
            id=command.dataset_id or "",
            name=command.name,
            data_source_id=command.data_source_id,
            source_type=DatasetSourceType.QUERY,
            query=command.query,
            parameters=list(command.parameters),
        )
        self._ensure_dataset_can_be_added(report, proposed)
        validation = self.sql_validator.validate_dataset(proposed)
        fields: tuple[DatasetField, ...] = ()
        warnings = validation.warnings
        if command.discover_fields:
            discovery = self.query_discovery_service.discover_fields(
                dataset=proposed,
                data_source=self.get_data_source(report, command.data_source_id),
                parameter_values=parameter_values,
            )
            fields = discovery.fields
            warnings += discovery.warnings
            proposed = self._copy_dataset(proposed, fields=list(fields))

        dataset = report.add_dataset(proposed)
        return DatasetConfigurationResult(
            dataset=dataset,
            fields=tuple(dataset.fields),
            parameters=tuple(dataset.parameters),
            warnings=warnings,
        )

    def validate_query_dataset_configuration(
        self,
        *,
        query: str,
        parameters: tuple[QueryParameter, ...] = (),
    ) -> SQLValidationResult:
        """Validate an unsaved query and report parameters before definitions are complete."""
        result = self.sql_validator.validate(query)
        declared_names = [parameter.name for parameter in parameters]
        seen: set[str] = set()
        for name in declared_names:
            normalized = name.casefold()
            if normalized in seen:
                raise InvalidSQLParameterError(
                    f"Dataset contains a duplicate parameter declaration: {name}."
                )
            seen.add(normalized)
        referenced = {name.casefold() for name in result.parameters}
        warnings = tuple(
            f"Dataset parameter {name!r} is not referenced by the SQL query."
            for name in declared_names
            if name.casefold() not in referenced
        )
        return replace(result, warnings=result.warnings + warnings)

    def validate_dataset_query(self, report: Report, dataset_id: str) -> SQLValidationResult:
        """Validate an existing query dataset without opening a connection."""
        dataset = self.get_dataset(report, dataset_id)
        self._require_dataset_type(dataset, DatasetSourceType.QUERY)
        return self.sql_validator.validate_dataset(dataset)

    def discover_query_fields(
        self,
        report: Report,
        dataset_id: str,
        *,
        parameter_values: Mapping[str, object] | None = None,
    ) -> QueryFieldDiscoveryResult:
        """Discover fields for an existing query dataset without mutating it."""
        dataset = self.get_dataset(report, dataset_id)
        self._require_dataset_type(dataset, DatasetSourceType.QUERY)
        data_source = self.get_data_source(report, dataset.data_source_id)
        return self.query_discovery_service.discover_fields(
            dataset=dataset,
            data_source=data_source,
            parameter_values=parameter_values,
        )

    def discover_query_configuration_fields(
        self,
        *,
        data_source: ReportDataSource,
        query: str,
        parameters: tuple[QueryParameter, ...],
        parameter_values: Mapping[str, object] | None = None,
    ) -> QueryFieldDiscoveryResult:
        """Discover fields for an unsaved query configuration."""
        dataset = ReportDataset(
            name="Query discovery",
            data_source_id=data_source.id,
            source_type=DatasetSourceType.QUERY,
            query=query,
            parameters=list(parameters),
        )
        return self.query_discovery_service.discover_fields(
            dataset=dataset,
            data_source=data_source,
            parameter_values=parameter_values,
        )

    def apply_discovered_fields(
        self,
        report: Report,
        dataset_id: str,
        discovery_result: QueryFieldDiscoveryResult,
    ) -> DatasetConfigurationResult:
        """Atomically apply discovered fields to an existing query dataset."""
        dataset, index = self._find_dataset(report, dataset_id)
        self._require_dataset_type(dataset, DatasetSourceType.QUERY)
        if discovery_result.dataset_id != dataset.id:
            raise StaleDiscoveryResultError(
                "The discovery result does not belong to the target dataset."
            )
        replacement = self.query_discovery_service.apply_fields(dataset, discovery_result)
        warnings = discovery_result.warnings + self._binding_change_warnings(
            report, dataset.id, dataset.fields, replacement.fields
        )
        self._replace_dataset(report, index, replacement)
        return DatasetConfigurationResult(
            dataset=replacement,
            fields=tuple(replacement.fields),
            parameters=tuple(replacement.parameters),
            warnings=warnings,
            changes=self._field_changes(dataset.fields, replacement.fields),
        )

    def update_query_dataset(
        self,
        report: Report,
        dataset_id: str,
        *,
        name: str | None = None,
        query: str | None = None,
        parameters: tuple[QueryParameter, ...] | None = None,
    ) -> DatasetConfigurationResult:
        """Update a query dataset atomically; clear fields when SQL text changes."""
        dataset, index = self._find_dataset(report, dataset_id)
        self._require_dataset_type(dataset, DatasetSourceType.QUERY)
        query_changed = query is not None and query != dataset.query
        replacement = self._copy_dataset(
            dataset,
            name=name if name is not None else dataset.name,
            query=query if query is not None else dataset.query,
            parameters=list(parameters) if parameters is not None else list(dataset.parameters),
            fields=[] if query_changed else list(dataset.fields),
        )
        self.sql_validator.validate_dataset(replacement)
        warnings = self._binding_change_warnings(
            report, dataset.id, dataset.fields, replacement.fields
        )
        self._replace_dataset(report, index, replacement)
        return DatasetConfigurationResult(
            dataset=replacement,
            fields=tuple(replacement.fields),
            parameters=tuple(replacement.parameters),
            warnings=warnings,
        )

    def update_view_dataset(
        self,
        report: Report,
        dataset_id: str,
        *,
        name: str | None = None,
        view_name: str | None = None,
        refresh_fields: bool = True,
        metadata_policy: MetadataAccessPolicy | None = None,
    ) -> DatasetConfigurationResult:
        """Update a view dataset atomically and refresh fields when requested."""
        dataset, index = self._find_dataset(report, dataset_id)
        self._require_dataset_type(dataset, DatasetSourceType.VIEW)
        final_view = view_name if view_name is not None else dataset.view_name
        fields = list(dataset.fields)
        warnings: tuple[str, ...] = ()
        if refresh_fields or view_name is not None:
            data_source = self.get_data_source(report, dataset.data_source_id)
            schema = self._metadata_service(data_source, metadata_policy).inspect_view(
                data_source,
                final_view or "",
            )
            discovered, warnings = self._fields_from_columns(schema.columns)
            fields = list(discovered)
        replacement = self._copy_dataset(
            dataset,
            name=name if name is not None else dataset.name,
            view_name=final_view,
            fields=fields,
            parameters=[],
        )
        warnings += self._binding_change_warnings(
            report, dataset.id, dataset.fields, replacement.fields
        )
        self._replace_dataset(report, index, replacement)
        return DatasetConfigurationResult(
            dataset=replacement,
            fields=tuple(replacement.fields),
            parameters=tuple(replacement.parameters),
            warnings=warnings,
            changes=self._field_changes(dataset.fields, replacement.fields),
        )

    def replace_query_parameters(
        self,
        report: Report,
        dataset_id: str,
        parameters: tuple[QueryParameter, ...],
    ) -> ReportDataset:
        """Replace all query parameter definitions after SQL consistency validation."""
        dataset, index = self._find_dataset(report, dataset_id)
        self._require_dataset_type(dataset, DatasetSourceType.QUERY)
        replacement = self._copy_dataset(dataset, parameters=list(parameters))
        self.sql_validator.validate_dataset(replacement)
        self._replace_dataset(report, index, replacement)
        return replacement

    def add_query_parameter(
        self,
        report: Report,
        dataset_id: str,
        parameter: QueryParameter,
    ) -> ReportDataset:
        """Append a query parameter and revalidate the dataset."""
        dataset = self.get_dataset(report, dataset_id)
        return self.replace_query_parameters(
            report,
            dataset_id,
            (*tuple(dataset.parameters), parameter),
        )

    def update_query_parameter(
        self,
        report: Report,
        dataset_id: str,
        parameter_name: str,
        replacement: QueryParameter,
    ) -> ReportDataset:
        """Replace one query parameter and revalidate the dataset."""
        dataset = self.get_dataset(report, dataset_id)
        parameters = list(dataset.parameters)
        for index, parameter in enumerate(parameters):
            if parameter.name == parameter_name:
                parameters[index] = replacement
                return self.replace_query_parameters(report, dataset_id, tuple(parameters))
        raise InvalidDatasetOperationError(f"The query parameter {parameter_name!r} was not found.")

    def remove_query_parameter(
        self,
        report: Report,
        dataset_id: str,
        parameter_name: str,
    ) -> ReportDataset:
        """Remove one query parameter and revalidate the dataset."""
        dataset = self.get_dataset(report, dataset_id)
        parameters = tuple(
            parameter for parameter in dataset.parameters if parameter.name != parameter_name
        )
        if len(parameters) == len(dataset.parameters):
            raise InvalidDatasetOperationError(
                f"The query parameter {parameter_name!r} was not found."
            )
        return self.replace_query_parameters(report, dataset_id, parameters)

    def remove_dataset(self, report: Report, dataset_id: str) -> DataManagementResult:
        """Remove a dataset without altering its parent data source."""
        self.get_dataset(report, dataset_id)
        self._assert_dataset_not_referenced(report, dataset_id)
        report.remove_dataset(dataset_id)
        return DataManagementResult(success=True, message=f"Removed dataset {dataset_id!r}.")

    def _metadata_service(
        self,
        data_source: ReportDataSource,
        policy: MetadataAccessPolicy | None,
    ) -> MySQLMetadataService:
        provider = self.provider_registry.get(data_source.type)
        if data_source.type != MYSQL_DATA_SOURCE_TYPE:
            raise UnsupportedDataSourceProviderError(
                f"The provider {data_source.type!r} does not support reporting-view discovery."
            )
        return MySQLMetadataService(provider=provider, policy=policy)

    def _data_source_from_create_command(
        self,
        command: CreateMySQLDataSourceCommand,
    ) -> ReportDataSource:
        return ReportDataSource(
            id=command.data_source_id or "",
            name=command.name,
            type=MYSQL_DATA_SOURCE_TYPE,
            connection=MySQLConnectionConfig(
                host=command.host,
                port=command.port,
                database=command.database,
                username=command.username,
                password=command.password,
                password_ref=command.password_ref,
                charset=command.charset,
                connect_timeout=command.connect_timeout,
                query_timeout=command.query_timeout,
            ),
        )

    @staticmethod
    def _data_source_summary(data_source: ReportDataSource) -> DataSourceSummary:
        config = (
            data_source.connection
            if isinstance(data_source.connection, MySQLConnectionConfig)
            else None
        )
        return DataSourceSummary(
            id=data_source.id,
            name=data_source.name,
            type=data_source.type,
            host=config.host if config is not None else None,
            port=config.port if config is not None else None,
            database=config.database if config is not None else None,
            username=config.username if config is not None else None,
            charset=config.charset if config is not None else None,
            connect_timeout=config.connect_timeout if config is not None else None,
            query_timeout=config.query_timeout if config is not None else None,
            password_configured=bool(config and config.password is not None),
            password_ref_configured=bool(config and config.password_ref is not None),
        )

    @staticmethod
    def _dataset_summary(dataset: ReportDataset) -> DatasetSummary:
        source_type = dataset.source_type.value
        source_label = (
            dataset.view_name
            if dataset.source_type is DatasetSourceType.VIEW
            else "Custom SELECT query"
        )
        return DatasetSummary(
            id=dataset.id,
            name=dataset.name,
            data_source_id=dataset.data_source_id,
            source_type=source_type,
            source_label=source_label or "",
            field_count=len(dataset.fields),
            parameter_count=len(dataset.parameters),
        )

    @staticmethod
    def _fields_from_columns(
        columns: tuple[DatabaseColumnInfo, ...],
    ) -> tuple[tuple[DatasetField, ...], tuple[str, ...]]:
        fields: list[DatasetField] = []
        warnings: list[str] = []
        for column in columns:
            if column.normalized_type == "unknown":
                warnings.append(
                    f"Column {column.name!r} has unknown database type {column.database_type!r}."
                )
            fields.append(
                DatasetField(
                    name=column.name,
                    data_type=column.normalized_type,
                    nullable=column.nullable,
                    source_name=column.source_name,
                )
            )
        return tuple(fields), tuple(warnings)

    @staticmethod
    def _find_data_source(report: Report, data_source_id: str) -> tuple[ReportDataSource, int]:
        for index, data_source in enumerate(report.data_sources):
            if data_source.id == data_source_id:
                return data_source, index
        raise DataSourceNotFoundError(f"The data source {data_source_id!r} was not found.")

    @staticmethod
    def _find_dataset(report: Report, dataset_id: str) -> tuple[ReportDataset, int]:
        for index, dataset in enumerate(report.datasets):
            if dataset.id == dataset_id:
                return dataset, index
        raise DatasetNotFoundError(f"The dataset {dataset_id!r} was not found.")

    @staticmethod
    def _replace_data_source(
        report: Report,
        index: int,
        replacement: ReportDataSource,
    ) -> None:
        proposed = list(report.data_sources)
        proposed[index] = replacement
        ids = [item.id for item in proposed]
        if len(ids) != len(set(ids)):
            raise DataManagementValidationError("Report data-source IDs must be unique.")
        report.data_sources[index] = replacement

    def _replace_dataset(self, report: Report, index: int, replacement: ReportDataset) -> None:
        proposed = list(report.datasets)
        proposed[index] = replacement
        for other_index, dataset in enumerate(proposed):
            if other_index == index:
                continue
            if dataset.id == replacement.id:
                raise DataManagementValidationError(
                    f"The dataset {replacement.id!r} already exists."
                )
            if dataset.name.casefold() == replacement.name.casefold():
                raise DataManagementValidationError(
                    f"The dataset name {replacement.name!r} already exists."
                )
        if report.get_data_source(replacement.data_source_id) is None:
            raise DataManagementValidationError(
                f"The dataset references missing data source {replacement.data_source_id!r}."
            )
        report.datasets[index] = replacement

    @staticmethod
    def _ensure_dataset_can_be_added(report: Report, dataset: ReportDataset) -> None:
        if report.get_data_source(dataset.data_source_id) is None:
            raise DataManagementValidationError(
                f"The dataset references missing data source {dataset.data_source_id!r}."
            )
        if any(existing.id == dataset.id for existing in report.datasets):
            raise DataManagementValidationError(f"The dataset {dataset.id!r} already exists.")
        if any(existing.name.casefold() == dataset.name.casefold() for existing in report.datasets):
            raise DataManagementValidationError(
                f"The dataset name {dataset.name!r} already exists."
            )

    @staticmethod
    def _copy_dataset(dataset: ReportDataset, **overrides: object) -> ReportDataset:
        values: dict[str, object] = {
            "id": dataset.id,
            "name": dataset.name,
            "data_source_id": dataset.data_source_id,
            "source_type": dataset.source_type,
            "view_name": dataset.view_name,
            "query": dataset.query,
            "fields": list(dataset.fields),
            "parameters": list(dataset.parameters),
        }
        values.update(overrides)
        return ReportDataset(**values)

    @staticmethod
    def _require_dataset_type(
        dataset: ReportDataset,
        source_type: DatasetSourceType,
    ) -> None:
        if dataset.source_type is not source_type:
            display = (
                "view-based" if dataset.source_type is DatasetSourceType.VIEW else "query-based"
            )
            raise DatasetTypeMismatchError(
                f"The dataset {dataset.id!r} is {display} and cannot be used for this operation."
            )

    @staticmethod
    def _field_changes(
        before: list[DatasetField],
        after: list[DatasetField],
    ) -> DatasetFieldChangeSummary:
        before_by_key = {field.name.casefold(): field for field in before}
        after_by_key = {field.name.casefold(): field for field in after}
        added = tuple(field.name for key, field in after_by_key.items() if key not in before_by_key)
        removed = tuple(
            field.name for key, field in before_by_key.items() if key not in after_by_key
        )
        changed = tuple(
            after_by_key[key].name
            for key in after_by_key.keys() & before_by_key.keys()
            if after_by_key[key].data_type != before_by_key[key].data_type
            or after_by_key[key].nullable != before_by_key[key].nullable
        )
        return DatasetFieldChangeSummary(added=added, removed=removed, changed=changed)

    @staticmethod
    def _assert_dataset_not_referenced(report: Report, dataset_id: str) -> None:
        service = ReportBindingService()
        objects = service.dataset_references(report, dataset_id)
        bands = service.dataset_band_references(report, dataset_id)
        if objects or bands:
            raise DatasetInUseError(
                f"The dataset {dataset_id!r} is used by {len(objects)} report objects "
                f"and {len(bands)} bands and cannot be removed."
            )

    @staticmethod
    def _binding_change_warnings(
        report: Report,
        dataset_id: str,
        before: list[DatasetField],
        after: list[DatasetField],
    ) -> tuple[str, ...]:
        references = ReportBindingService().dataset_references(report, dataset_id)
        if not references:
            return ()
        before_by_name = {field.name: field for field in before}
        after_by_name = {field.name: field for field in after}
        warnings: list[str] = []
        for report_object in references:
            field_name = report_object.dataset_binding.field
            previous = before_by_name.get(field_name)
            current = after_by_name.get(field_name)
            if current is None:
                warnings.append(
                    f"Binding on object {report_object.id!r} now references missing field "
                    f"{field_name!r}; the binding was preserved."
                )
            elif previous is not None and previous.data_type != current.data_type:
                warnings.append(
                    f"Bound field {field_name!r} on object {report_object.id!r} changed "
                    f"type from {previous.data_type!r} to {current.data_type!r}."
                )
        return tuple(warnings)


DesignerDataService = DataSourceManagementService
