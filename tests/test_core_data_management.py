from __future__ import annotations

from contextlib import contextmanager
from datetime import date

import pytest

from slim_report_core import (
    ConnectionTestResult,
    CreateMySQLDataSourceCommand,
    CreateQueryDatasetCommand,
    CreateViewDatasetCommand,
    DatasetField,
    DatasetNotFoundError,
    DatasetTypeMismatchError,
    DataSourceInUseError,
    DataSourceManagementService,
    DataSourceNotFoundError,
    DataSourceProviderRegistry,
    DiscoveredColumn,
    InvalidSQLParameterError,
    MetadataQueryError,
    MySQLConnectionConfig,
    MySQLDialect,
    ProviderFieldDiscoveryResult,
    QueryFieldDiscoveryPolicy,
    QueryFieldDiscoveryResult,
    QueryFieldDiscoveryService,
    QueryParameter,
    Report,
    ReportDataset,
    ReportDataSource,
    SQLValidator,
    StaleDiscoveryResultError,
    UnsupportedStatementError,
    UpdateMySQLDataSourceCommand,
)
from slim_report_core.data_source_providers.metadata import (
    DatabaseColumnInfo,
    DatabaseViewSchema,
)


class FakeMetadataCursor:
    def __init__(self, connection: FakeMetadataConnection) -> None:
        self.connection = connection
        self.last_query = ""
        self.closed = False

    def execute(self, query: str, parameters: tuple[object, ...]) -> None:
        self.last_query = query
        self.connection.queries.append((query, parameters))
        if self.connection.error is not None:
            raise self.connection.error

    def fetchall(self) -> list[tuple[object, ...]]:
        if "information_schema.VIEWS" in self.last_query:
            if "TABLE_NAME = %s" in self.last_query:
                return [
                    ("lis", "report_patient_results", "NO", "report_user@%", "DEFINER"),
                ]
            return [
                ("lis", "report_patient_results", "NO", "report_user@%", "DEFINER"),
                ("lis", "report_orders", "NO", "report_user@%", "DEFINER"),
            ]
        if "information_schema.COLUMNS" in self.last_query:
            return [
                (
                    "lis",
                    "report_patient_results",
                    "patient_id",
                    1,
                    None,
                    "NO",
                    "int",
                    "int",
                    None,
                    10,
                    0,
                    None,
                    "",
                ),
                (
                    "lis",
                    "report_patient_results",
                    "patient_name",
                    2,
                    None,
                    "YES",
                    "varchar",
                    "varchar(100)",
                    100,
                    None,
                    None,
                    None,
                    "",
                ),
            ]
        return []

    def close(self) -> None:
        self.closed = True
        self.connection.closed_cursors += 1


class FakeMetadataConnection:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.queries: list[tuple[str, tuple[object, ...]]] = []
        self.closed = False
        self.closed_cursors = 0

    def cursor(self) -> FakeMetadataCursor:
        return FakeMetadataCursor(self)

    def close(self) -> None:
        self.closed = True


class FakeMySQLProvider:
    provider_type = "mysql"
    dialect_name = "mysql"

    def __init__(
        self,
        *,
        discovery_result: ProviderFieldDiscoveryResult | None = None,
        metadata_connection: FakeMetadataConnection | None = None,
        connection_result: ConnectionTestResult | None = None,
        discovery_error: Exception | None = None,
    ) -> None:
        self.discovery_result = discovery_result or ProviderFieldDiscoveryResult(
            columns=(
                DiscoveredColumn("orderid", 1, "LONG", "integer", nullable=False),
                DiscoveredColumn("pname", 2, "VAR_STRING", "string", nullable=True),
            ),
            sample_row_count=1,
            elapsed_ms=2.0,
        )
        self.metadata_connection = metadata_connection or FakeMetadataConnection()
        self.connection_result = connection_result or ConnectionTestResult(
            success=True,
            provider="mysql",
            message="ok",
            read_only_verified=True,
        )
        self.discovery_error = discovery_error
        self.tested: list[ReportDataSource] = []
        self.discovery_calls: list[dict[str, object]] = []

    def test_connection(self, data_source: ReportDataSource) -> ConnectionTestResult:
        self.tested.append(data_source)
        return self.connection_result

    @contextmanager
    def connection(self, data_source: ReportDataSource):  # type: ignore[no-untyped-def]
        try:
            yield self.metadata_connection
        finally:
            self.metadata_connection.close()

    def discover_query_fields(
        self,
        *,
        data_source: ReportDataSource,
        sql: str,
        parameters: dict[str, object],
        policy: QueryFieldDiscoveryPolicy,
    ) -> ProviderFieldDiscoveryResult:
        self.discovery_calls.append(
            {"data_source": data_source, "sql": sql, "parameters": parameters, "policy": policy}
        )
        if self.discovery_error is not None:
            raise self.discovery_error
        return self.discovery_result


def data_source() -> ReportDataSource:
    return ReportDataSource(
        id="main_mysql",
        name="Main MySQL",
        type="mysql",
        connection=MySQLConnectionConfig(
            host="db.internal",
            database="lis",
            username="report_user",
            password="secret",
            password_ref="MYSQL_PASSWORD",
        ),
    )


def query_dataset() -> ReportDataset:
    return ReportDataset(
        id="orders",
        name="Orders",
        data_source_id="main_mysql",
        source_type="query",
        query="SELECT orderid FROM report_orders WHERE orderdate >= :date_from",
        parameters=(QueryParameter("date_from", "date", required=True),),
        fields=(DatasetField("old_field"),),
    )


def report_with_source() -> Report:
    report = Report("Managed")
    report.add_data_source(data_source())
    return report


def management_service(provider: FakeMySQLProvider) -> DataSourceManagementService:
    registry = DataSourceProviderRegistry()
    registry.register(provider)  # type: ignore[arg-type]
    validator = SQLValidator(MySQLDialect())
    discovery = QueryFieldDiscoveryService(registry, validator)
    return DataSourceManagementService(
        provider_registry=registry,
        sql_validator=validator,
        query_discovery_service=discovery,
    )


def test_create_list_update_and_serialize_mysql_data_source() -> None:
    provider = FakeMySQLProvider()
    service = management_service(provider)
    report = Report("Managed")

    created = service.create_mysql_data_source(
        report,
        CreateMySQLDataSourceCommand(
            name="Main MySQL",
            host="db.internal",
            port=3306,
            database="lis",
            username="report_user",
            password="secret",
            password_ref="MYSQL_PASSWORD",
        ),
    )

    assert created.id == "data_source_main_mysql"
    assert "password" not in created.to_dict()["connection"]
    summary = service.list_data_sources(report)[0]
    assert summary.password_configured is True
    assert summary.password_ref_configured is True
    assert "secret" not in repr(summary)

    updated = service.update_mysql_data_source(
        report,
        UpdateMySQLDataSourceCommand(
            data_source_id=created.id,
            host="db2.internal",
            clear_runtime_password=True,
            clear_password_ref=True,
            query_timeout=12,
        ),
    )

    assert updated.connection.host == "db2.internal"
    assert updated.connection.password is None
    assert updated.connection.password_ref is None
    assert updated.connection.query_timeout == 12


def test_create_data_source_failure_is_atomic_and_connection_test_does_not_mutate() -> None:
    provider = FakeMySQLProvider()
    service = management_service(provider)
    report = Report("Managed")

    with pytest.raises(Exception, match="port"):
        service.create_mysql_data_source(
            report,
            CreateMySQLDataSourceCommand(
                name="Bad",
                host="db.internal",
                port=70000,
                database="lis",
                username="report_user",
            ),
        )

    assert report.data_sources == []
    source = service.create_mysql_data_source(
        report,
        CreateMySQLDataSourceCommand(
            name="Main MySQL",
            host="db.internal",
            port=3306,
            database="lis",
            username="report_user",
        ),
    )
    before = source.to_dict(include_password=True)

    result = service.test_data_source_connection(report, source.id)

    assert result.success is True
    assert source.to_dict(include_password=True) == before
    assert provider.tested == [source]
    with pytest.raises(DataSourceNotFoundError):
        service.test_data_source_connection(report, "missing")


def test_remove_data_source_rejects_in_use_and_cascades_explicitly() -> None:
    service = management_service(FakeMySQLProvider())
    report = report_with_source()
    report.add_dataset(
        ReportDataset(
            id="patients",
            name="Patients",
            data_source_id="main_mysql",
            source_type="view",
            view_name="report_patient_results",
        )
    )

    with pytest.raises(DataSourceInUseError, match="cascade"):
        service.remove_data_source(report, "main_mysql")

    result = service.remove_data_source(report, "main_mysql", cascade=True)

    assert result.success is True
    assert report.data_sources == []
    assert report.datasets == []


def test_list_and_inspect_views_use_metadata_service_without_rows() -> None:
    connection = FakeMetadataConnection()
    service = management_service(FakeMySQLProvider(metadata_connection=connection))
    report = report_with_source()

    views = service.list_available_views(report, "main_mysql")
    schema = service.inspect_view(report, "main_mysql", "report_patient_results")

    assert [view.view_name for view in views] == ["report_orders", "report_patient_results"]
    assert isinstance(schema, DatabaseViewSchema)
    assert [column.name for column in schema.columns] == ["patient_id", "patient_name"]
    assert connection.closed
    assert connection.closed_cursors >= 2


def test_create_and_refresh_view_dataset_are_atomic() -> None:
    provider = FakeMySQLProvider()
    service = management_service(provider)
    report = report_with_source()

    result = service.create_view_dataset(
        report,
        CreateViewDatasetCommand(
            name="Patient Results",
            data_source_id="main_mysql",
            view_name="report_patient_results",
        ),
    )

    assert result.dataset.source_type.value == "view"
    assert [field.name for field in result.fields] == ["patient_id", "patient_name"]
    assert report.get_dataset(result.dataset.id) is result.dataset

    provider.metadata_connection = FakeMetadataConnection(error=RuntimeError("raw secret"))
    before = list(report.datasets)
    with pytest.raises(MetadataQueryError):
        service.refresh_view_dataset_fields(report, result.dataset.id)
    assert report.datasets == before


def test_create_query_dataset_validation_and_discovery() -> None:
    provider = FakeMySQLProvider()
    service = management_service(provider)
    report = report_with_source()

    result = service.create_query_dataset(
        report,
        CreateQueryDatasetCommand(
            name="Orders",
            data_source_id="main_mysql",
            query="SELECT orderid, pname FROM report_orders WHERE orderdate >= :date_from",
            parameters=(QueryParameter("date_from", "date", required=True),),
            discover_fields=True,
        ),
        parameter_values={"date_from": date(2026, 1, 1)},
    )

    assert [field.name for field in result.fields] == ["orderid", "pname"]
    assert provider.discovery_calls[0]["parameters"] == {"date_from": date(2026, 1, 1)}
    assert "2026" not in result.dataset.to_dict()["query"]


def test_create_query_dataset_failure_does_not_insert() -> None:
    service = management_service(FakeMySQLProvider())
    report = report_with_source()

    with pytest.raises(UnsupportedStatementError, match=r"only SELECT|UPDATE"):
        service.create_query_dataset(
            report,
            CreateQueryDatasetCommand(
                name="Unsafe",
                data_source_id="main_mysql",
                query="UPDATE patients SET name='x'",
            ),
        )

    assert report.datasets == []


def test_validate_discover_and_apply_query_fields_are_explicit() -> None:
    provider = FakeMySQLProvider()
    service = management_service(provider)
    report = report_with_source()
    dataset = report.add_dataset(query_dataset())

    validation = service.validate_dataset_query(report, dataset.id)
    discovery = service.discover_query_fields(
        report,
        dataset.id,
        parameter_values={"date_from": date(2026, 1, 1)},
    )

    assert validation.parameters == ("date_from",)
    assert [field.name for field in dataset.fields] == ["old_field"]
    applied = service.apply_discovered_fields(report, dataset.id, discovery)
    assert [field.name for field in applied.fields] == ["orderid", "pname"]

    with pytest.raises(StaleDiscoveryResultError):
        service.apply_discovered_fields(
            report,
            dataset.id,
            QueryFieldDiscoveryResult(
                dataset_id="other",
                dataset_name="Other",
                provider="mysql",
                dialect="mysql",
                fields=(),
                parameters=(),
                sample_row_count=0,
                elapsed_ms=0.0,
            ),
        )


def test_update_query_dataset_and_parameter_management_are_atomic() -> None:
    service = management_service(FakeMySQLProvider())
    report = report_with_source()
    dataset = report.add_dataset(query_dataset())

    renamed = service.update_query_dataset(report, dataset.id, name="Order Listing")
    assert renamed.fields == tuple(dataset.fields) or renamed.fields == dataset.fields

    changed = service.update_query_dataset(
        report,
        dataset.id,
        query="SELECT orderid FROM report_orders WHERE orderdate BETWEEN :date_from AND :date_to",
        parameters=(
            QueryParameter("date_from", "date", required=True),
            QueryParameter("date_to", "date", required=True),
        ),
    )
    assert changed.fields == ()

    with pytest.raises(InvalidSQLParameterError):
        service.remove_query_parameter(report, dataset.id, "date_to")
    assert [parameter.name for parameter in report.get_dataset(dataset.id).parameters] == [
        "date_from",
        "date_to",
    ]


def test_update_view_dataset_rejects_query_dataset_and_remove_dataset_preserves_source() -> None:
    service = management_service(FakeMySQLProvider())
    report = report_with_source()
    dataset = report.add_dataset(query_dataset())

    with pytest.raises(DatasetTypeMismatchError):
        service.update_view_dataset(report, dataset.id, view_name="report_patient_results")

    result = service.remove_dataset(report, dataset.id)

    assert result.success is True
    assert report.get_dataset(dataset.id) is None
    assert report.get_data_source("main_mysql") is not None
    with pytest.raises(DatasetNotFoundError):
        service.get_dataset(report, dataset.id)


def test_summaries_do_not_include_full_sql_or_credentials() -> None:
    service = management_service(FakeMySQLProvider())
    report = report_with_source()
    report.add_dataset(query_dataset())

    data_source_summary = service.list_data_sources(report)[0]
    dataset_summary = service.list_datasets(report)[0]

    assert "secret" not in repr(data_source_summary)
    assert "MYSQL_PASSWORD" not in repr(data_source_summary)
    assert dataset_summary.source_label == "Custom SELECT query"
    assert "report_orders" not in repr(dataset_summary)


def test_view_metadata_columns_convert_to_dataset_fields() -> None:
    service = management_service(FakeMySQLProvider())
    fields, warnings = service._fields_from_columns(
        (
            DatabaseColumnInfo(
                name="mystery",
                ordinal_position=1,
                database_type="weird",
                normalized_type="unknown",
                nullable=True,
            ),
        )
    )

    assert fields == (DatasetField("mystery", "unknown", source_name=None),)
    assert warnings


def test_view_dataset_creation_without_discovery_defers_database_access() -> None:
    provider = FakeMySQLProvider(metadata_connection=FakeMetadataConnection(error=RuntimeError()))
    service = management_service(provider)
    report = report_with_source()

    result = service.create_view_dataset(
        report,
        CreateViewDatasetCommand(
            name="Deferred",
            data_source_id="main_mysql",
            view_name="report_patient_results",
            discover_fields=False,
        ),
    )

    assert result.fields == ()
    assert provider.metadata_connection.queries == []


def test_missing_objects_raise_focused_errors() -> None:
    service = management_service(FakeMySQLProvider())
    report = Report("Managed")

    with pytest.raises(DataSourceNotFoundError):
        service.get_data_source(report, "missing")
    with pytest.raises(DatasetNotFoundError):
        service.get_dataset(report, "missing")
    with pytest.raises(DataSourceNotFoundError):
        service.create_query_dataset(
            report,
            CreateQueryDatasetCommand(
                name="Missing Source",
                data_source_id="missing",
                query="SELECT 1",
            ),
        )
