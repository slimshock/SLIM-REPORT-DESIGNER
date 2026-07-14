from __future__ import annotations

from contextlib import contextmanager
from dataclasses import FrozenInstanceError
from datetime import date, datetime, time
from decimal import Decimal

import pytest

from slim_report_core import (
    DatasetField,
    DataSourceProviderRegistry,
    DiscoveredColumn,
    DuplicateOutputColumnError,
    InvalidQueryParameterValueError,
    MissingQueryParameterValueError,
    MySQLConnectionConfig,
    MySQLDataSourceProvider,
    MySQLDialect,
    ProviderFieldDiscoveryResult,
    QueryExecutionTimeoutError,
    QueryFieldDiscoveryPolicy,
    QueryFieldDiscoveryResult,
    QueryFieldDiscoveryService,
    QueryParameter,
    QueryParameterError,
    QueryParameterValueConverter,
    QueryReturnedNoColumnsError,
    ReportDataset,
    ReportDataSource,
    SQLValidator,
    TooManyOutputColumnsError,
    UnsupportedDataSourceProviderError,
)
from slim_report_core.data_source_providers.mysql.discovery import (
    MySQLQueryFieldDiscovery,
    convert_mysql_named_placeholders,
)


class FakeDiscoveryProvider:
    provider_type = "mysql"
    dialect_name = "mysql"

    def __init__(
        self,
        result: ProviderFieldDiscoveryResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result or ProviderFieldDiscoveryResult(
            columns=(
                DiscoveredColumn(
                    name="patient_id",
                    ordinal_position=1,
                    database_type="LONG",
                    normalized_type="integer",
                    nullable=False,
                ),
            ),
            sample_row_count=1,
            elapsed_ms=1.5,
        )
        self.error = error
        self.calls: list[dict[str, object]] = []

    def test_connection(self, data_source: ReportDataSource) -> object:
        raise AssertionError("not used")

    @contextmanager
    def connection(self, data_source: ReportDataSource):  # type: ignore[no-untyped-def]
        raise AssertionError("generic service opened a connection")
        yield

    def discover_query_fields(
        self,
        *,
        data_source: ReportDataSource,
        sql: str,
        parameters: dict[str, object],
        policy: QueryFieldDiscoveryPolicy,
    ) -> ProviderFieldDiscoveryResult:
        self.calls.append(
            {
                "data_source": data_source,
                "sql": sql,
                "parameters": parameters,
                "policy": policy,
            }
        )
        if self.error is not None:
            raise self.error
        return self.result


class UnsupportedProvider:
    provider_type = "mysql"

    def test_connection(self, data_source: ReportDataSource) -> object:
        raise AssertionError("not used")

    @contextmanager
    def connection(self, data_source: ReportDataSource):  # type: ignore[no-untyped-def]
        yield object()


def data_source(provider_type: str = "mysql") -> ReportDataSource:
    return ReportDataSource(
        id="main_mysql",
        name="Main MySQL",
        type=provider_type,
        connection=MySQLConnectionConfig(
            host="db.internal",
            database="lis",
            username="report_user",
            password="secret",
        ),
    )


def dataset(**overrides: object) -> ReportDataset:
    values: dict[str, object] = {
        "id": "patient_results",
        "name": "Patient Results",
        "data_source_id": "main_mysql",
        "source_type": "query",
        "query": "SELECT patient_id FROM report_patient_results WHERE orderdate >= :date_from",
        "parameters": [QueryParameter("date_from", "date", required=True)],
    }
    values.update(overrides)
    return ReportDataset(**values)


def discovery_service(provider: object, **policy_overrides: object) -> QueryFieldDiscoveryService:
    registry = DataSourceProviderRegistry()
    registry.register(provider)  # type: ignore[arg-type]
    return QueryFieldDiscoveryService(
        provider_registry=registry,
        sql_validator=SQLValidator(MySQLDialect()),
        policy=QueryFieldDiscoveryPolicy(**policy_overrides),
    )


def test_discover_fields_validates_converts_and_returns_immutable_result() -> None:
    provider = FakeDiscoveryProvider()
    service = discovery_service(provider)

    result = service.discover_fields(
        dataset=dataset(),
        data_source=data_source(),
        parameter_values={"date_from": "2026-01-01"},
    )

    assert isinstance(result, QueryFieldDiscoveryResult)
    assert result.dataset_id == "patient_results"
    assert result.provider == "mysql"
    assert result.dialect == "mysql"
    assert result.parameters == ("date_from",)
    assert result.fields == (DatasetField("patient_id", "integer", nullable=False),)
    assert provider.calls[0]["sql"] == (
        "SELECT patient_id FROM report_patient_results WHERE orderdate >= :date_from"
    )
    assert provider.calls[0]["parameters"] == {"date_from": date(2026, 1, 1)}
    with pytest.raises(FrozenInstanceError):
        result.dataset_id = "other"  # type: ignore[misc]


def test_unsafe_sql_never_reaches_provider() -> None:
    provider = FakeDiscoveryProvider()
    service = discovery_service(provider)

    with pytest.raises(Exception, match=r"UPDATE|only SELECT"):
        service.discover_fields(
            dataset=dataset(query="UPDATE patients SET name = :date_from"),
            data_source=data_source(),
            parameter_values={"date_from": "2026-01-01"},
        )

    assert provider.calls == []


def test_discovery_rejects_unknown_and_missing_parameter_values_without_leaking_values() -> None:
    service = discovery_service(FakeDiscoveryProvider())

    with pytest.raises(QueryParameterError, match=":extra") as unknown:
        service.discover_fields(
            dataset=dataset(),
            data_source=data_source(),
            parameter_values={"date_from": "2026-01-01", "extra": "very-secret"},
        )
    assert "very-secret" not in str(unknown.value)

    with pytest.raises(MissingQueryParameterValueError) as missing:
        service.discover_fields(dataset=dataset(), data_source=data_source())
    assert "secret" not in str(missing.value)


def test_discovery_rejects_invalid_provider_and_mismatched_dataset_source() -> None:
    registry = DataSourceProviderRegistry()
    registry.register(UnsupportedProvider())  # type: ignore[arg-type]
    service = QueryFieldDiscoveryService(registry, SQLValidator(MySQLDialect()))

    with pytest.raises(UnsupportedDataSourceProviderError, match="does not support"):
        service.discover_fields(
            dataset=dataset(),
            data_source=data_source(),
            parameter_values={"date_from": "2026-01-01"},
        )

    with pytest.raises(Exception, match="does not match"):
        discovery_service(FakeDiscoveryProvider()).discover_fields(
            dataset=dataset(data_source_id="other"),
            data_source=data_source(),
            parameter_values={"date_from": "2026-01-01"},
        )


def test_discovery_result_validation_rejects_no_columns_duplicates_and_limits() -> None:
    with pytest.raises(QueryReturnedNoColumnsError):
        discovery_service(
            FakeDiscoveryProvider(ProviderFieldDiscoveryResult((), 0, 1.0))
        ).discover_fields(
            dataset=dataset(),
            data_source=data_source(),
            parameter_values={"date_from": "2026-01-01"},
        )

    duplicate = ProviderFieldDiscoveryResult(
        columns=(
            DiscoveredColumn("id", 1, "LONG", "integer"),
            DiscoveredColumn("ID", 2, "LONG", "integer"),
        ),
        sample_row_count=1,
        elapsed_ms=1.0,
    )
    with pytest.raises(DuplicateOutputColumnError, match=r"id|ID"):
        discovery_service(FakeDiscoveryProvider(duplicate)).discover_fields(
            dataset=dataset(),
            data_source=data_source(),
            parameter_values={"date_from": "2026-01-01"},
        )

    too_many = ProviderFieldDiscoveryResult(
        columns=(
            DiscoveredColumn("a", 1, "LONG", "integer"),
            DiscoveredColumn("b", 2, "LONG", "integer"),
        ),
        sample_row_count=1,
        elapsed_ms=1.0,
    )
    with pytest.raises(TooManyOutputColumnsError, match="2 columns"):
        discovery_service(FakeDiscoveryProvider(too_many), max_columns=1).discover_fields(
            dataset=dataset(),
            data_source=data_source(),
            parameter_values={"date_from": "2026-01-01"},
        )


def test_apply_fields_is_explicit_and_preserves_dataset_metadata() -> None:
    source_dataset = dataset(fields=[DatasetField("old")])
    service = discovery_service(FakeDiscoveryProvider())
    result = service.discover_fields(
        dataset=source_dataset,
        data_source=data_source(),
        parameter_values={"date_from": "2026-01-01"},
    )

    assert source_dataset.fields == [DatasetField("old")]
    updated = service.apply_fields(source_dataset, result)

    assert updated is not source_dataset
    assert updated.id == source_dataset.id
    assert updated.query == source_dataset.query
    assert updated.parameters == source_dataset.parameters
    assert updated.fields == list(result.fields)


@pytest.mark.parametrize(
    "parameter, raw, expected",
    [
        (QueryParameter("p", "string", required=True), 123, "123"),
        (QueryParameter("p", "integer", required=True), "42", 42),
        (QueryParameter("p", "float", required=True), "3.5", 3.5),
        (QueryParameter("p", "decimal", required=True), "10.25", Decimal("10.25")),
        (QueryParameter("p", "boolean", required=True), "yes", True),
        (QueryParameter("p", "boolean", required=True), "0", False),
        (QueryParameter("p", "date", required=True), "2026-01-02", date(2026, 1, 2)),
        (QueryParameter("p", "time", required=True), "12:30:00", time(12, 30)),
        (
            QueryParameter("p", "datetime", required=True),
            "2026-01-02T03:04:05",
            datetime(2026, 1, 2, 3, 4, 5),
        ),
    ],
)
def test_parameter_value_converter_supported_types(
    parameter: QueryParameter,
    raw: object,
    expected: object,
) -> None:
    assert QueryParameterValueConverter().convert(parameter=parameter, value=raw) == expected


@pytest.mark.parametrize("raw", ["maybe", "2", object()])
def test_parameter_value_converter_rejects_ambiguous_boolean(raw: object) -> None:
    with pytest.raises(InvalidQueryParameterValueError):
        QueryParameterValueConverter().convert(
            parameter=QueryParameter("active", "boolean", required=True),
            value=raw,
        )


def test_parameter_value_converter_handles_defaults_and_optional_missing() -> None:
    converter = QueryParameterValueConverter()

    assert converter.convert(parameter=QueryParameter("limit", "integer", default="5")) == 5
    assert converter.convert(parameter=QueryParameter("optional", "string")) is None


@pytest.mark.parametrize(
    "sql, expected",
    [
        ("SELECT :id", "SELECT %(id)s"),
        ("SELECT :id, :id", "SELECT %(id)s, %(id)s"),
        ("SELECT ':not_a_parameter'", "SELECT ':not_a_parameter'"),
        ("SELECT 'http://example.com'", "SELECT 'http://example.com'"),
        ("SELECT '12:30:00'", "SELECT '12:30:00'"),
        ("SELECT column_name::text", "SELECT column_name::text"),
        ("SELECT /* :comment */ :id", "SELECT /* :comment */ %(id)s"),
        ("SELECT -- :comment\n:id", "SELECT -- :comment\n%(id)s"),
    ],
)
def test_mysql_placeholder_conversion_is_token_aware(sql: str, expected: str) -> None:
    assert convert_mysql_named_placeholders(sql) == expected


class FakeCursor:
    def __init__(
        self,
        description: tuple[tuple[object, ...], ...],
        rows: list[tuple[object, ...]],
    ) -> None:
        self.description = description
        self.rows = rows
        self.executed: tuple[str, dict[str, object]] | None = None
        self.closed = False
        self.fetchall_called = False

    def execute(self, sql: str, parameters: dict[str, object]) -> None:
        self.executed = (sql, parameters)

    def fetchmany(self, size: int) -> list[tuple[object, ...]]:
        return self.rows[:size]

    def fetchall(self) -> list[tuple[object, ...]]:
        self.fetchall_called = True
        raise AssertionError("fetchall must not be used")

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self.cursor_instance = cursor
        self.closed = False

    def cursor(self) -> FakeCursor:
        return self.cursor_instance

    def close(self) -> None:
        self.closed = True


class FakeConnectionProvider(MySQLDataSourceProvider):
    def __init__(self, connection: FakeConnection) -> None:
        super().__init__()
        self.connection_instance = connection

    @contextmanager
    def connection(self, data_source: ReportDataSource):  # type: ignore[no-untyped-def]
        try:
            yield self.connection_instance
        finally:
            self.connection_instance.close()


def test_mysql_discovery_executes_bound_query_fetches_limited_rows_and_closes_resources() -> None:
    cursor = FakeCursor(
        description=(("id", 3, None, 11, None, None, False),),
        rows=[(1,), (2,)],
    )
    connection = FakeConnection(cursor)
    discovery = MySQLQueryFieldDiscovery(FakeConnectionProvider(connection))

    result = discovery.discover_query_fields(
        data_source=data_source(),
        sql="SELECT id FROM patients WHERE id = :id",
        parameters={"id": 1},
        policy=QueryFieldDiscoveryPolicy(max_preview_rows=1),
    )

    assert cursor.executed == ("SELECT id FROM patients WHERE id = %(id)s", {"id": 1})
    assert result.columns[0].name == "id"
    assert result.columns[0].normalized_type == "integer"
    assert result.sample_row_count == 1
    assert cursor.closed
    assert connection.closed
    assert not cursor.fetchall_called


def test_mysql_discovery_maps_unknown_types_to_warning_and_timeout_errors() -> None:
    discovery = MySQLQueryFieldDiscovery(FakeConnectionProvider(FakeConnection(FakeCursor((), []))))
    columns, warnings = discovery.columns_from_description((("mystery", 99999, None, None),))

    assert columns[0].normalized_type == "unknown"
    assert warnings

    class TimeoutCursor(FakeCursor):
        def execute(self, sql: str, parameters: dict[str, object]) -> None:
            raise TimeoutError("timed out with hidden-secret")

    cursor = TimeoutCursor(description=(), rows=[])
    with pytest.raises(QueryExecutionTimeoutError) as caught:
        MySQLQueryFieldDiscovery(FakeConnectionProvider(FakeConnection(cursor))).discover_query_fields(
            data_source=data_source(),
            sql="SELECT :id",
            parameters={"id": "hidden-secret"},
            policy=QueryFieldDiscoveryPolicy(),
        )

    assert "hidden-secret" not in str(caught.value)


@pytest.mark.parametrize(
    "type_code, label, expected",
    [
        (253, "VAR_STRING", "string"),
        (3, "LONG", "integer"),
        (5, "DOUBLE", "float"),
        (246, "NEWDECIMAL", "decimal"),
        (10, "DATE", "date"),
        (11, "TIME", "time"),
        (12, "DATETIME", "datetime"),
        (7, "TIMESTAMP", "datetime"),
        (252, "BLOB", "binary"),
        (245, "JSON", "string"),
        (255, "GEOMETRY", "unknown"),
    ],
)
def test_mysql_driver_type_code_mapping(type_code: int, label: str, expected: str) -> None:
    discovery = MySQLQueryFieldDiscovery(FakeConnectionProvider(FakeConnection(FakeCursor((), []))))
    columns, _ = discovery.columns_from_description(((label.lower(), type_code, None, None),))

    assert columns[0].database_type == label
    assert columns[0].normalized_type == expected
