from __future__ import annotations

import copy
import json
from contextlib import contextmanager
from dataclasses import FrozenInstanceError
from datetime import date, datetime, time
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from slim_report_core import (
    DatasetExecutionCancellationToken,
    DatasetExecutionCancelledError,
    DatasetExecutionConfigurationError,
    DatasetExecutionOptions,
    DatasetExecutionPolicy,
    DatasetExecutionProviderError,
    DatasetExecutionService,
    DatasetExecutionTimeoutError,
    DatasetField,
    DatasetNotExecutableError,
    DatasetResultLimitError,
    DatasetRowShapeError,
    DatasetSchemaMismatchError,
    DatasetValueTypeError,
    DataSourceProviderRegistry,
    MetadataAccessPolicy,
    MySQLDialect,
    QueryParameter,
    Report,
    ReportDataset,
    ReportDataSource,
    RuntimeParameterMissingError,
    RuntimeParameterResolver,
    SQLValidationError,
    SQLValidator,
)
from slim_report_core.data_source_providers.mysql.execution import (
    build_mysql_view_select,
    quote_mysql_identifier_part,
    quote_mysql_qualified_identifier,
)
from slim_report_core.data_source_providers.mysql.provider import MySQLDataSourceProvider
from slim_report_core.dataset_execution.policy import effective_execution_configuration
from slim_report_core.dataset_execution.provider import ProviderDatasetExecutionRequest


class FakeRawStream:
    def __init__(
        self,
        column_names: tuple[str, ...],
        rows: list[object],
        *,
        token: DatasetExecutionCancellationToken | None = None,
        cancel_on_fetch: int | None = None,
        error: Exception | None = None,
    ) -> None:
        self.column_names = column_names
        self.rows = list(rows)
        self.token = token
        self.cancel_on_fetch = cancel_on_fetch
        self.error = error
        self.fetch_sizes: list[int] = []
        self.fetch_count = 0
        self.close_count = 0

    def fetchmany(self, size: int) -> list[object]:
        self.fetch_count += 1
        self.fetch_sizes.append(size)
        if self.cancel_on_fetch == self.fetch_count and self.token is not None:
            self.token.cancel()
        if self.error is not None:
            raise self.error
        result = self.rows[:size]
        del self.rows[:size]
        return result

    def close(self) -> None:
        self.close_count += 1


class FakeExecutionProvider:
    provider_type = "mysql"
    dialect_name = "mysql"

    def __init__(self, raw_stream: FakeRawStream) -> None:
        self.raw_stream = raw_stream
        self.requests: list[ProviderDatasetExecutionRequest] = []

    def open_dataset_stream(self, request: ProviderDatasetExecutionRequest) -> FakeRawStream:
        self.requests.append(request)
        return self.raw_stream


def source() -> ReportDataSource:
    return ReportDataSource(
        id="mysql",
        name="Reporting",
        connection={
            "host": "localhost",
            "database": "lis",
            "username": "reader",
            "password": "runtime-password",
            "queryTimeout": 20,
        },
    )


def query_dataset(
    *,
    query: str = "SELECT order_id, amount FROM report_orders WHERE client_id = :client_id",
    fields: list[DatasetField] | None = None,
) -> ReportDataset:
    return ReportDataset(
        id="orders",
        name="Daily Orders",
        data_source_id="mysql",
        source_type="query",
        query=query,
        fields=fields
        if fields is not None
        else [
            DatasetField("order_id", "integer", False),
            DatasetField("amount", "decimal", True),
        ],
        parameters=[QueryParameter("client_id", "integer", required=True)],
    )


def view_dataset(*, view_name: str = "report_orders") -> ReportDataset:
    return ReportDataset(
        id="orders_view",
        name="Orders View",
        data_source_id="mysql",
        source_type="view",
        view_name=view_name,
        fields=[
            DatasetField("order-id", "integer", False, source_name="order`id"),
            DatasetField("name", "string", True),
        ],
    )


def make_report(dataset: ReportDataset) -> Report:
    return Report(data_sources=[source()], datasets=[dataset])


def execution_service(
    raw_stream: FakeRawStream,
    *,
    policy: DatasetExecutionPolicy | None = None,
    metadata_policy: MetadataAccessPolicy | None = None,
) -> tuple[DatasetExecutionService, FakeExecutionProvider]:
    provider = FakeExecutionProvider(raw_stream)
    registry = DataSourceProviderRegistry()
    registry.register(provider)
    return (
        DatasetExecutionService(
            provider_registry=registry,
            sql_validator=SQLValidator(MySQLDialect()),
            parameter_resolver=RuntimeParameterResolver(),
            policy=policy,
            metadata_policy=metadata_policy,
        ),
        provider,
    )


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({"max_rows": 0}, "max_rows"),
        ({"max_rows": -1}, "max_rows"),
        ({"max_rows": True}, "max_rows"),
        ({"batch_size": 0}, "batch_size"),
        ({"max_execution_timeout_seconds": 0}, "max_execution_timeout_seconds"),
        ({"max_columns": 0}, "max_columns"),
        ({"max_cell_bytes": 0}, "max_cell_bytes"),
        ({"max_total_bytes": 0}, "max_total_bytes"),
    ],
)
def test_execution_policy_rejects_invalid_limits(values: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        DatasetExecutionPolicy(**values)  # type: ignore[arg-type]


def test_execution_policy_relationships_and_frozen_state() -> None:
    with pytest.raises(ValueError, match="batch_size"):
        DatasetExecutionPolicy(max_rows=10, batch_size=11)
    with pytest.raises(ValueError, match="max_total_bytes"):
        DatasetExecutionPolicy(max_cell_bytes=10, max_total_bytes=9)
    policy = DatasetExecutionPolicy()
    with pytest.raises(FrozenInstanceError):
        policy.max_rows = 1  # type: ignore[misc]


def test_effective_options_are_stricter_and_do_not_mutate_policy() -> None:
    policy = DatasetExecutionPolicy(max_rows=100, batch_size=20)
    effective = effective_execution_configuration(
        policy,
        DatasetExecutionOptions(max_rows=50, batch_size=10, timeout_seconds=5),
        data_source_timeout=8,
    )

    assert (effective.max_rows, effective.batch_size, effective.timeout_seconds) == (50, 10, 5)
    assert (policy.max_rows, policy.batch_size) == (100, 20)
    with pytest.raises(DatasetExecutionConfigurationError):
        effective_execution_configuration(
            policy,
            DatasetExecutionOptions(max_rows=101),
            data_source_timeout=8,
        )


def test_query_execution_resolves_values_and_preserves_report() -> None:
    raw = FakeRawStream(
        ("ORDER_ID", "amount"),
        [(1, Decimal("10.25")), (2, None)],
    )
    service, provider = execution_service(raw)
    report = make_report(query_dataset())
    before = copy.deepcopy(report.template.to_dict())

    with service.open_dataset(report, "orders", parameter_values={"client_id": "12"}) as stream:
        rows = list(stream)
        summary = stream.summary()

    request = provider.requests[0]
    assert request.sql == report.datasets[0].query
    assert dict(request.parameters) == {"client_id": 12}
    assert request.data_source.connection.query_timeout == 20
    assert request.data_source is not report.data_sources[0]
    assert [dict(row.values) for row in rows] == [
        {"order_id": 1, "amount": Decimal("10.25")},
        {"order_id": 2, "amount": None},
    ]
    assert [row.index for row in rows] == [1, 2]
    assert summary.row_count == 2
    assert not summary.truncated
    assert raw.close_count == 1
    assert report.template.to_dict() == before
    serialized = json.dumps(report.template.to_dict()).lower()
    assert "runtime-password" not in serialized
    assert '"client_id": 12' not in serialized


def test_validation_and_parameters_fail_before_provider_open() -> None:
    raw = FakeRawStream(("order_id", "amount"), [])
    service, provider = execution_service(raw)
    unsafe = make_report(query_dataset(query="UPDATE report_orders SET amount = 1"))
    missing = make_report(query_dataset())

    with pytest.raises(SQLValidationError):
        service.open_dataset(unsafe, "orders", parameter_values={"client_id": 1})
    with pytest.raises(RuntimeParameterMissingError):
        service.open_dataset(missing, "orders")

    assert provider.requests == []


def test_missing_fields_duplicate_fields_and_options_fail_before_open() -> None:
    raw = FakeRawStream(("order_id",), [])
    service, provider = execution_service(raw)
    empty = make_report(query_dataset(fields=[]))
    duplicate_dataset = query_dataset()
    duplicate_dataset.fields.append(DatasetField("ORDER_ID", "integer"))
    duplicate = make_report(duplicate_dataset)

    with pytest.raises(DatasetNotExecutableError, match="no discovered fields"):
        service.open_dataset(empty, "orders", parameter_values={"client_id": 1})
    with pytest.raises(DatasetNotExecutableError, match="duplicate"):
        service.open_dataset(duplicate, "orders", parameter_values={"client_id": 1})
    with pytest.raises(DatasetExecutionConfigurationError):
        service.open_dataset(
            make_report(query_dataset()),
            "orders",
            parameter_values={"client_id": 1},
            options=DatasetExecutionOptions(max_rows=10_001),
        )
    assert provider.requests == []


def test_corrupted_stored_field_metadata_and_view_parameters_fail_before_open() -> None:
    raw = FakeRawStream(("order_id", "amount"), [])
    service, provider = execution_service(raw)
    invalid_type = query_dataset()
    invalid_type.fields[0].data_type = "private-custom-type"
    invalid_nullable = query_dataset()
    invalid_nullable.fields[0].nullable = "yes"  # type: ignore[assignment]
    invalid_source = query_dataset()
    invalid_source.fields[0].source_name = object()  # type: ignore[assignment]
    parameterized_view = view_dataset()
    parameterized_view.parameters.append(QueryParameter("client_id", "integer"))

    with pytest.raises(DatasetNotExecutableError, match="unsupported stored type"):
        service.open_dataset(make_report(invalid_type), "orders", parameter_values={"client_id": 1})
    with pytest.raises(DatasetNotExecutableError, match="nullable metadata"):
        service.open_dataset(
            make_report(invalid_nullable), "orders", parameter_values={"client_id": 1}
        )
    with pytest.raises(DatasetNotExecutableError, match="source-name metadata"):
        service.open_dataset(
            make_report(invalid_source), "orders", parameter_values={"client_id": 1}
        )
    with pytest.raises(DatasetNotExecutableError, match="cannot define"):
        service.open_dataset(make_report(parameterized_view), "orders_view")
    assert provider.requests == []


def test_missing_relationship_and_unsupported_capability_fail_safely() -> None:
    raw = FakeRawStream(("order_id", "amount"), [])
    service, provider = execution_service(raw)
    report = make_report(query_dataset())

    with pytest.raises(DatasetNotExecutableError, match="was not found"):
        service.open_dataset(report, "missing", parameter_values={"client_id": 1})
    report.data_sources.clear()
    with pytest.raises(DatasetNotExecutableError, match="data source was not found"):
        service.open_dataset(report, "orders", parameter_values={"client_id": 1})
    assert provider.requests == []

    class UnsupportedProvider:
        provider_type = "mysql"

    registry = DataSourceProviderRegistry()
    registry.register(UnsupportedProvider())  # type: ignore[arg-type]
    unsupported = DatasetExecutionService(
        provider_registry=registry,
        sql_validator=SQLValidator(MySQLDialect()),
        parameter_resolver=RuntimeParameterResolver(),
    )
    with pytest.raises(DatasetExecutionProviderError, match="does not support"):
        unsupported.open_dataset(
            make_report(query_dataset()),
            "orders",
            parameter_values={"client_id": 1},
        )


def test_service_requires_mysql_validator() -> None:
    raw = FakeRawStream(("order_id", "amount"), [])
    provider = FakeExecutionProvider(raw)
    registry = DataSourceProviderRegistry()
    registry.register(provider)
    validator = SQLValidator(MySQLDialect())
    validator.dialect = SimpleNamespace(name="other")  # type: ignore[assignment]

    with pytest.raises(DatasetExecutionConfigurationError, match="MySQL SQL validator"):
        DatasetExecutionService(
            provider_registry=registry,
            sql_validator=validator,
            parameter_resolver=RuntimeParameterResolver(),
        )


def test_schema_mismatch_closes_before_fetching() -> None:
    raw = FakeRawStream(("order_id", "renamed"), [(1, "x")])
    service, _provider = execution_service(raw)

    with pytest.raises(DatasetSchemaMismatchError, match="no longer matches"):
        service.open_dataset(
            make_report(query_dataset()),
            "orders",
            parameter_values={"client_id": 1},
        )

    assert raw.fetch_sizes == []
    assert raw.close_count == 1


@pytest.mark.parametrize(
    "returned_names",
    [
        ("order_id",),
        ("order_id", "amount", "extra"),
        ("amount", "order_id"),
        ("order_id", "ORDER_ID"),
    ],
)
def test_schema_shape_changes_are_rejected_before_fetch(returned_names: tuple[str, ...]) -> None:
    raw = FakeRawStream(returned_names, [(1, 2)])
    service, _provider = execution_service(raw)

    with pytest.raises(DatasetSchemaMismatchError):
        service.open_dataset(
            make_report(query_dataset()),
            "orders",
            parameter_values={"client_id": 1},
        )
    assert raw.fetch_sizes == []
    assert raw.close_count == 1


def test_mapping_rows_use_stored_field_casing_and_summary_lifecycle() -> None:
    fields = [DatasetField("Order_ID", "integer"), DatasetField("Amount", "decimal")]
    dataset = query_dataset(fields=fields)
    raw = FakeRawStream(("order_id", "amount"), [{"ORDER_ID": 1, "AMOUNT": "10.25"}])
    service, provider = execution_service(raw)
    report = make_report(dataset)

    stream = service.open_dataset(report, "orders", parameter_values={"client_id": 1})
    assert stream.summary().row_count == 0
    row = next(stream)
    assert dict(row.values) == {"Order_ID": 1, "Amount": "10.25"}
    assert stream.summary().row_count == 1
    assert list(stream) == []
    stream.close()
    assert stream.summary().row_count == 1
    assert provider.requests[0].data_source.connection.query_timeout == 20


def test_execution_options_reduce_timeout_without_mutating_data_source() -> None:
    raw = FakeRawStream(("order_id", "amount"), [])
    service, provider = execution_service(raw)
    report = make_report(query_dataset())

    with service.open_dataset(
        report,
        "orders",
        parameter_values={"client_id": 1},
        options=DatasetExecutionOptions(max_rows=5, batch_size=1, timeout_seconds=4),
    ) as stream:
        list(stream)

    request = provider.requests[0]
    assert (request.max_rows, request.batch_size, request.timeout_seconds) == (5, 1, 4)
    assert request.data_source.connection.query_timeout == 4
    assert report.data_sources[0].connection.query_timeout == 20


def test_batches_row_limit_and_truncation_lookahead() -> None:
    policy = DatasetExecutionPolicy(
        max_rows=3,
        batch_size=2,
        max_cell_bytes=100,
        max_total_bytes=1000,
    )
    raw = FakeRawStream(
        ("order_id", "amount"),
        [(1, 1), (2, 2), (3, 3), (4, 4)],
    )
    service, _provider = execution_service(raw, policy=policy)

    with service.open_dataset(
        make_report(query_dataset()),
        "orders",
        parameter_values={"client_id": 1},
    ) as stream:
        batches = list(stream.iter_batches())
        summary = stream.summary()

    assert [[row.index for row in batch.rows] for batch in batches] == [[1, 2], [3]]
    assert [batch.start_index for batch in batches] == [1, 3]
    assert raw.fetch_sizes == [2, 1, 1]
    assert summary.row_count == 3
    assert summary.truncated
    assert "3 rows" in summary.warnings[0]


def test_exact_row_limit_is_not_truncated() -> None:
    policy = DatasetExecutionPolicy(
        max_rows=2,
        batch_size=2,
        max_cell_bytes=100,
        max_total_bytes=1000,
    )
    raw = FakeRawStream(("order_id", "amount"), [(1, 1), (2, 2)])
    service, _provider = execution_service(raw, policy=policy)

    with service.open_dataset(
        make_report(query_dataset()),
        "orders",
        parameter_values={"client_id": 1},
    ) as stream:
        assert len(list(stream)) == 2
        assert not stream.summary().truncated

    assert raw.fetch_sizes == [2, 1]


@pytest.mark.parametrize(
    "value",
    [
        None,
        "text",
        b"bytes",
        bytearray(b"bytearray"),
        memoryview(b"memory"),
        True,
        10,
        1.5,
        Decimal("1.250"),
        date(2026, 1, 1),
        time(8, 30),
        datetime(2026, 1, 1, 8, 30),
    ],
)
def test_supported_row_values(value: object) -> None:
    raw = FakeRawStream(("value",), [(value,)])
    service, _provider = execution_service(raw)
    dataset = query_dataset(
        query="SELECT value FROM report_orders WHERE client_id = :client_id",
        fields=[DatasetField("value")],
    )

    with service.open_dataset(
        make_report(dataset),
        "orders",
        parameter_values={"client_id": 1},
    ) as stream:
        result = next(stream).values["value"]

    expected = bytes(value) if isinstance(value, (bytearray, memoryview)) else value
    assert result == expected


@pytest.mark.parametrize("value", [float("nan"), float("inf"), Decimal("NaN"), object()])
def test_unsafe_row_values_are_rejected_without_exposure(value: object) -> None:
    raw = FakeRawStream(("value",), [(value,)])
    service, _provider = execution_service(raw)
    dataset = query_dataset(
        query="SELECT value FROM report_orders WHERE client_id = :client_id",
        fields=[DatasetField("value")],
    )

    with service.open_dataset(
        make_report(dataset),
        "orders",
        parameter_values={"client_id": 1},
    ) as stream:
        with pytest.raises(DatasetValueTypeError) as raised:
            next(stream)

    assert str(value) not in str(raised.value)
    assert raw.close_count == 1


def test_row_shape_cell_and_total_size_limits() -> None:
    small_policy = DatasetExecutionPolicy(
        max_rows=10,
        batch_size=2,
        max_cell_bytes=5,
        max_total_bytes=10,
    )
    malformed = FakeRawStream(("value",), [(1, 2)])
    service, _provider = execution_service(malformed, policy=small_policy)
    dataset = query_dataset(
        query="SELECT value FROM report_orders WHERE client_id = :client_id",
        fields=[DatasetField("value")],
    )
    with service.open_dataset(
        make_report(dataset), "orders", parameter_values={"client_id": 1}
    ) as stream:
        with pytest.raises(DatasetRowShapeError):
            next(stream)

    malformed_mapping = FakeRawStream(("value",), [{1: "private"}])
    service, _provider = execution_service(malformed_mapping, policy=small_policy)
    with service.open_dataset(
        make_report(dataset), "orders", parameter_values={"client_id": 1}
    ) as stream:
        with pytest.raises(DatasetRowShapeError):
            next(stream)

    oversized = FakeRawStream(("value",), [("private-large-value",)])
    service, _provider = execution_service(oversized, policy=small_policy)
    with service.open_dataset(
        make_report(dataset), "orders", parameter_values={"client_id": 1}
    ) as stream:
        with pytest.raises(DatasetResultLimitError) as raised:
            next(stream)
    assert "private-large-value" not in str(raised.value)

    total_policy = DatasetExecutionPolicy(
        max_rows=10,
        batch_size=2,
        max_cell_bytes=6,
        max_total_bytes=10,
    )
    total = FakeRawStream(("value",), [("123456",), ("abcdef",)])
    service, _provider = execution_service(total, policy=total_policy)
    with service.open_dataset(
        make_report(dataset), "orders", parameter_values={"client_id": 1}
    ) as stream:
        assert next(stream).index == 1
        with pytest.raises(DatasetResultLimitError):
            next(stream)
        assert stream.summary().row_count == 1


def test_binary_policy_and_consumer_exception_cleanup() -> None:
    policy = DatasetExecutionPolicy(allow_binary_values=False)
    raw = FakeRawStream(("value",), [(b"private",)])
    service, _provider = execution_service(raw, policy=policy)
    dataset = query_dataset(
        query="SELECT value FROM report_orders WHERE client_id = :client_id",
        fields=[DatasetField("value", "binary")],
    )
    with service.open_dataset(
        make_report(dataset), "orders", parameter_values={"client_id": 1}
    ) as stream:
        with pytest.raises(DatasetValueTypeError):
            next(stream)
    assert raw.close_count == 1

    raw = FakeRawStream(("value",), [(1,), (2,)])
    service, _provider = execution_service(raw)
    with pytest.raises(RuntimeError, match="consumer failed"):
        with service.open_dataset(
            make_report(dataset), "orders", parameter_values={"client_id": 1}
        ) as stream:
            next(stream)
            raise RuntimeError("consumer failed")
    assert raw.close_count == 1


def test_cancellation_before_open_and_between_batches() -> None:
    token = DatasetExecutionCancellationToken()
    token.cancel()
    token.cancel()
    raw = FakeRawStream(("order_id", "amount"), [])
    service, provider = execution_service(raw)
    with pytest.raises(DatasetExecutionCancelledError):
        service.open_dataset(
            make_report(query_dataset()),
            "orders",
            parameter_values={"client_id": 1},
            cancellation_token=token,
        )
    assert provider.requests == []

    token = DatasetExecutionCancellationToken()
    raw = FakeRawStream(
        ("order_id", "amount"),
        [(1, 1), (2, 2), (3, 3)],
        token=token,
        cancel_on_fetch=2,
    )
    policy = DatasetExecutionPolicy(max_rows=10, batch_size=2)
    service, _provider = execution_service(raw, policy=policy)
    with service.open_dataset(
        make_report(query_dataset()),
        "orders",
        parameter_values={"client_id": 1},
        cancellation_token=token,
    ) as stream:
        assert [next(stream).index, next(stream).index] == [1, 2]
        with pytest.raises(DatasetExecutionCancelledError):
            next(stream)
        assert stream.summary().cancelled
    assert raw.close_count >= 1


def test_view_sql_is_policy_checked_and_uses_explicit_quoted_fields() -> None:
    raw = FakeRawStream(("order-id", "name"), [])
    service, provider = execution_service(raw)

    with service.open_dataset(make_report(view_dataset()), "orders_view") as stream:
        assert list(stream) == []

    sql = provider.requests[0].sql
    assert sql == "SELECT `order``id` AS `order-id`, `name` FROM `lis`.`report_orders`"
    assert "*" not in sql
    assert dict(provider.requests[0].parameters) == {}

    disallowed_service, disallowed_provider = execution_service(
        FakeRawStream(("order-id", "name"), []),
        metadata_policy=MetadataAccessPolicy(allowed_view_names=("approved_view",)),
    )
    with pytest.raises(DatasetNotExecutableError, match="not available"):
        disallowed_service.open_dataset(make_report(view_dataset()), "orders_view")
    assert disallowed_provider.requests == []


def test_cross_schema_view_policy() -> None:
    report = make_report(view_dataset(view_name="archive.report_orders"))
    denied, denied_provider = execution_service(FakeRawStream(("order-id", "name"), []))
    with pytest.raises(DatasetNotExecutableError):
        denied.open_dataset(report, "orders_view")
    assert denied_provider.requests == []

    allowed, provider = execution_service(
        FakeRawStream(("order-id", "name"), []),
        metadata_policy=MetadataAccessPolicy(
            allow_cross_schema=True,
            allowed_schemas=("archive",),
        ),
    )
    with allowed.open_dataset(report, "orders_view") as stream:
        list(stream)
    assert "FROM `archive`.`report_orders`" in provider.requests[0].sql


def test_identifier_quoting_rejects_invalid_parts() -> None:
    assert quote_mysql_identifier_part("column`name") == "`column``name`"
    assert quote_mysql_qualified_identifier("lis.report-orders") == "`lis`.`report-orders`"
    assert build_mysql_view_select("lis", "orders", [DatasetField("id")]).startswith(
        "SELECT `id` FROM"
    )
    with pytest.raises(DatasetExecutionProviderError):
        quote_mysql_identifier_part("")
    with pytest.raises(DatasetExecutionProviderError):
        quote_mysql_identifier_part("bad\x00name")


def test_primary_dataset_selection_uses_detail_band_then_requires_clarity() -> None:
    first = query_dataset()
    second = view_dataset()
    report = Report(
        data_sources=[source()],
        datasets=[first, second],
        bands=[
            {
                "id": "detail",
                "type": "detail",
                "dataBinding": {"datasetId": "orders_view"},
            }
        ],
    )
    service, _provider = execution_service(FakeRawStream(("order_id", "amount"), []))

    assert service.resolve_primary_dataset(report).id == "orders_view"
    assert service.resolve_primary_dataset(report, "orders").id == "orders"
    report.bands[0].dataset_id = None
    with pytest.raises(DatasetNotExecutableError, match="Select the dataset"):
        service.resolve_primary_dataset(report)


class FakeSSCursor:
    pass


class RecordingCursor:
    def __init__(self, events: list[str], *, fetch_error: Exception | None = None) -> None:
        self.events = events
        self.fetch_error = fetch_error
        self.description = (("note", 253), ("id", 3))
        self.executions: list[tuple[Any, ...]] = []

    def execute(self, *args: Any) -> None:
        self.events.append("execute")
        self.executions.append(args)

    def fetchmany(self, size: int) -> list[tuple[object, ...]]:
        self.events.append(f"fetchmany:{size}")
        if self.fetch_error is not None:
            raise self.fetch_error
        return []

    def fetchall(self) -> None:
        raise AssertionError("fetchall must never be called")

    def close(self) -> None:
        self.events.append("cursor-close")


class RecordingConnection:
    def __init__(self, cursor: RecordingCursor, events: list[str]) -> None:
        self.cursor_instance = cursor
        self.events = events
        self.cursor_classes: list[object] = []

    def cursor(self, cursor_class: object) -> RecordingCursor:
        self.cursor_classes.append(cursor_class)
        return self.cursor_instance

    def close(self) -> None:
        self.events.append("connection-close")


class RecordingMySQLProvider(MySQLDataSourceProvider):
    def __init__(self, connection: RecordingConnection) -> None:
        super().__init__()
        self.recording_connection = connection

    @staticmethod
    def _load_driver() -> object:
        return SimpleNamespace(cursors=SimpleNamespace(SSCursor=FakeSSCursor))

    @contextmanager
    def connection(self, data_source: ReportDataSource) -> Any:
        del data_source
        try:
            yield self.recording_connection
        finally:
            self.recording_connection.close()


def provider_request(
    *, cancellation_token: DatasetExecutionCancellationToken | None = None
) -> ProviderDatasetExecutionRequest:
    return ProviderDatasetExecutionRequest(
        dataset_id="orders",
        dataset_name="Orders",
        data_source=source(),
        source_type="query",
        sql=(
            "SELECT ':ignored' AS note, id FROM report_orders "
            "WHERE id = :id OR owner_id = :id /* :ignored */"
        ),
        parameters={"id": 7},
        fields=(DatasetField("note"), DatasetField("id", "integer")),
        max_rows=10,
        batch_size=2,
        timeout_seconds=5,
        max_columns=10,
        max_cell_bytes=100,
        max_total_bytes=1000,
        require_exact_field_schema=True,
        require_unique_column_names=True,
        allow_binary_values=True,
        allow_unknown_value_types=False,
        cancellation_token=cancellation_token,
    )


def test_mysql_provider_uses_sscursor_bound_values_and_cleanup_order() -> None:
    events: list[str] = []
    cursor = RecordingCursor(events)
    connection = RecordingConnection(cursor, events)
    provider = RecordingMySQLProvider(connection)

    stream = provider.open_dataset_stream(provider_request())
    assert connection.cursor_classes == [FakeSSCursor]
    sql, values = cursor.executions[0]
    assert "':ignored'" in sql
    assert "/* :ignored */" in sql
    assert sql.count("%(id)s") == 2
    assert values == {"id": 7}
    assert stream.fetchmany(2) == []
    stream.close()
    stream.close()

    assert events.count("execute") == 1
    assert events.index("cursor-close") < events.index("connection-close")


def test_mysql_timeout_is_safely_mapped_and_resources_close() -> None:
    events: list[str] = []
    cursor = RecordingCursor(events, fetch_error=TimeoutError("private timeout detail"))
    connection = RecordingConnection(cursor, events)
    provider = RecordingMySQLProvider(connection)
    registry = DataSourceProviderRegistry()
    registry.register(provider)
    service = DatasetExecutionService(
        provider_registry=registry,
        sql_validator=SQLValidator(MySQLDialect()),
        parameter_resolver=RuntimeParameterResolver(),
    )
    report = make_report(
        query_dataset(
            query=(
                "SELECT note, id FROM report_orders WHERE id = :client_id OR owner_id = :client_id"
            ),
            fields=[DatasetField("note"), DatasetField("id", "integer")],
        )
    )

    with service.open_dataset(
        report,
        "orders",
        parameter_values={"client_id": 7},
    ) as stream:
        with pytest.raises(DatasetExecutionTimeoutError) as raised:
            next(stream)

    assert "private timeout detail" not in str(raised.value)
    assert events.index("cursor-close") < events.index("connection-close")
