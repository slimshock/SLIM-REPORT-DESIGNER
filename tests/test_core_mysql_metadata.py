from __future__ import annotations

import logging
from contextlib import contextmanager
from dataclasses import FrozenInstanceError
from typing import Any

import pytest

from slim_report_core import (
    ConnectionTimeoutError,
    DatabaseColumnInfo,
    DatabaseUnavailableError,
    DatabaseViewInfo,
    DatabaseViewSchema,
    InvalidDatabaseError,
    InvalidViewIdentifierError,
    MetadataAccessDeniedError,
    MetadataAccessPolicy,
    MetadataLimitExceededError,
    MetadataQueryError,
    MySQLConnectionConfig,
    MySQLMetadataService,
    MySQLTypeMapper,
    ReadOnlySessionError,
    ReportDataSource,
    UnsupportedMetadataOperationError,
    ViewNotFoundError,
)


class FakeDriverError(Exception):
    pass


class FakeCursor:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection
        self.rows: object = ()
        self.closed = False

    def execute(self, sql: str, parameters: tuple[object, ...]) -> None:
        self.connection.executions.append((sql, parameters))
        if "information_schema.VIEWS" in sql:
            if self.connection.view_error is not None:
                raise self.connection.view_error
            if "TABLE_NAME = %s" in sql:
                requested_schema = str(parameters[0]).casefold()
                requested_view = str(parameters[1]).casefold()
                self.rows = tuple(
                    row
                    for row in self.connection.view_rows
                    if _row_value(row, 0, "TABLE_SCHEMA").casefold() == requested_schema
                    and _row_value(row, 1, "TABLE_NAME").casefold() == requested_view
                )
            else:
                self.rows = self.connection.view_rows
            return
        if "information_schema.COLUMNS" in sql:
            if self.connection.column_error is not None:
                raise self.connection.column_error
            self.rows = self.connection.column_rows
            return
        raise AssertionError(f"Unexpected SQL: {sql}")

    def fetchall(self) -> object:
        return self.rows

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    def __init__(
        self,
        *,
        view_rows: object = (),
        column_rows: object = (),
        view_error: Exception | None = None,
        column_error: Exception | None = None,
    ) -> None:
        self.view_rows = view_rows
        self.column_rows = column_rows
        self.view_error = view_error
        self.column_error = column_error
        self.executions: list[tuple[str, tuple[object, ...]]] = []
        self.cursors: list[FakeCursor] = []

    def cursor(self) -> FakeCursor:
        cursor = FakeCursor(self)
        self.cursors.append(cursor)
        return cursor


class FakeProvider:
    provider_type = "mysql"

    def __init__(self, connection: FakeConnection, error: Exception | None = None) -> None:
        self.fake_connection = connection
        self.error = error
        self.enter_count = 0
        self.exit_count = 0

    @contextmanager
    def connection(self, data_source: ReportDataSource):  # type: ignore[no-untyped-def]
        self.enter_count += 1
        try:
            if self.error is not None:
                raise self.error
            yield self.fake_connection
        finally:
            self.exit_count += 1


def _row_value(row: object, index: int, key: str) -> str:
    if isinstance(row, dict):
        return str(row[key])
    assert isinstance(row, tuple)
    return str(row[index])


def data_source(database: str = "lis") -> ReportDataSource:
    return ReportDataSource(
        name="Main MySQL",
        type="mysql",
        connection=MySQLConnectionConfig(
            database=database,
            username="report_user",
            password="secret",
        ),
    )


def view_row(
    name: str = "report_patient_results",
    *,
    schema: str = "lis",
    is_updatable: str = "NO",
    definer: str = "admin@localhost",
    security_type: str = "DEFINER",
    **extra: object,
) -> dict[str, object]:
    return {
        "TABLE_SCHEMA": schema,
        "TABLE_NAME": name,
        "IS_UPDATABLE": is_updatable,
        "DEFINER": definer,
        "SECURITY_TYPE": security_type,
        **extra,
    }


def column_row(
    name: str = "patient_id",
    *,
    ordinal: object = 1,
    schema: str = "lis",
    view: str = "report_patient_results",
    nullable: object = "NO",
    data_type: str = "bigint",
    column_type: str = "bigint unsigned",
    default: object = None,
    character_length: object = None,
    numeric_precision: object = 20,
    numeric_scale: object = 0,
    datetime_precision: object = None,
    comment: object = "Patient identifier",
    **extra: object,
) -> dict[str, object]:
    return {
        "TABLE_SCHEMA": schema,
        "TABLE_NAME": view,
        "COLUMN_NAME": name,
        "ORDINAL_POSITION": ordinal,
        "COLUMN_DEFAULT": default,
        "IS_NULLABLE": nullable,
        "DATA_TYPE": data_type,
        "COLUMN_TYPE": column_type,
        "CHARACTER_MAXIMUM_LENGTH": character_length,
        "NUMERIC_PRECISION": numeric_precision,
        "NUMERIC_SCALE": numeric_scale,
        "DATETIME_PRECISION": datetime_precision,
        "COLUMN_COMMENT": comment,
        **extra,
    }


def service(
    connection: FakeConnection,
    policy: MetadataAccessPolicy | None = None,
    provider_error: Exception | None = None,
) -> tuple[MySQLMetadataService, FakeProvider]:
    provider = FakeProvider(connection, error=provider_error)
    metadata = MySQLMetadataService(provider, policy=policy)  # type: ignore[arg-type]
    return metadata, provider


def test_list_views_uses_configured_schema_parameters_and_sorts_results() -> None:
    connection = FakeConnection(
        view_rows=(view_row("report_z"), view_row("report_A"), view_row("report_m"))
    )
    metadata, provider = service(connection)

    views = metadata.list_views(data_source())

    assert [item.view_name for item in views] == ["report_A", "report_m", "report_z"]
    assert all(isinstance(item, DatabaseViewInfo) for item in views)
    assert provider.enter_count == provider.exit_count == 1
    sql, parameters = connection.executions[0]
    assert "FROM information_schema.VIEWS" in sql
    assert "information_schema.TABLES" not in sql
    assert parameters == ("lis", 1001)
    assert "%s" in sql
    assert all(cursor.closed for cursor in connection.cursors)


def test_list_views_returns_empty_tuple() -> None:
    metadata, _ = service(FakeConnection())

    assert metadata.list_views(data_source()) == ()


def test_list_views_filters_system_schemas_and_nonmatching_rows_in_python() -> None:
    connection = FakeConnection(
        view_rows=(
            view_row("report_ok"),
            view_row("columns", schema="information_schema"),
            view_row("report_other", schema="archive"),
        )
    )
    metadata, _ = service(connection)

    assert [item.view_name for item in metadata.list_views(data_source())] == ["report_ok"]


@pytest.mark.parametrize(
    "policy, expected",
    [
        (MetadataAccessPolicy(allowed_view_names=("REPORT_DAILY",)), ["report_daily"]),
        (MetadataAccessPolicy(allowed_view_prefixes=("REPORT_",)), ["report_daily"]),
        (
            MetadataAccessPolicy(
                allowed_view_names=("special_view",),
                allowed_view_prefixes=("report_",),
            ),
            ["report_daily", "special_view"],
        ),
    ],
)
def test_list_views_applies_case_insensitive_exact_and_prefix_allowlists(
    policy: MetadataAccessPolicy,
    expected: list[str],
) -> None:
    connection = FakeConnection(
        view_rows=(
            view_row("report_daily"),
            view_row("special_view"),
            view_row("private_view"),
        )
    )
    metadata, _ = service(connection, policy)

    assert [item.view_name for item in metadata.list_views(data_source())] == expected


def test_definer_and_updatable_details_are_hidden_by_default() -> None:
    connection = FakeConnection(view_rows=(view_row(),))
    metadata, _ = service(connection)

    view = metadata.list_views(data_source())[0]

    assert view.is_updatable is None
    assert view.definer is None
    assert view.security_type is None


def test_policy_can_include_updatable_details() -> None:
    connection = FakeConnection(view_rows=(view_row(is_updatable="YES"),))
    policy = MetadataAccessPolicy(include_updatable_metadata=True)
    metadata, _ = service(connection, policy)

    view = metadata.list_views(data_source())[0]

    assert view.is_updatable is True
    assert view.definer == "admin@localhost"
    assert view.security_type == "DEFINER"


def test_view_limit_fails_instead_of_silently_truncating() -> None:
    connection = FakeConnection(view_rows=(view_row("one"), view_row("two")))
    metadata, _ = service(connection, MetadataAccessPolicy(max_views=1))

    with pytest.raises(MetadataLimitExceededError, match="limit of 1"):
        metadata.list_views(data_source())


def test_get_view_uses_parameter_binding_and_conceals_missing_views() -> None:
    connection = FakeConnection(view_rows=(view_row(),))
    metadata, _ = service(connection)

    found = metadata.get_view(data_source(), "report_patient_results")

    assert found.view_name == "report_patient_results"
    sql, parameters = connection.executions[0]
    assert parameters == ("lis", "report_patient_results")
    assert "TABLE_NAME = %s" in sql

    missing, _ = service(FakeConnection())
    with pytest.raises(ViewNotFoundError, match="was not found"):
        missing.get_view(data_source(), "report_missing")


def test_direct_disallowed_view_is_concealed_without_querying() -> None:
    connection = FakeConnection(view_rows=(view_row("private_view"),))
    policy = MetadataAccessPolicy(allowed_view_prefixes=("report_",))
    metadata, _ = service(connection, policy)

    with pytest.raises(ViewNotFoundError, match="private_view"):
        metadata.get_view(data_source(), "private_view")

    assert connection.executions == []


def test_inspect_view_reuses_one_connection_and_orders_columns() -> None:
    connection = FakeConnection(
        view_rows=(view_row(),),
        column_rows=(
            column_row("result", ordinal=2, data_type="varchar", column_type="varchar(255)"),
            column_row("patient_id", ordinal=1),
        ),
    )
    metadata, provider = service(connection)

    schema = metadata.inspect_view(data_source(), "report_patient_results")

    assert isinstance(schema, DatabaseViewSchema)
    assert schema.view.view_name == "report_patient_results"
    assert [item.name for item in schema.columns] == ["patient_id", "result"]
    assert [item.normalized_type for item in schema.columns] == ["integer", "string"]
    assert schema.columns[0].nullable is False
    assert provider.enter_count == provider.exit_count == 1
    assert len(connection.cursors) == 2
    assert all(cursor.closed for cursor in connection.cursors)


def test_list_view_columns_returns_empty_only_for_existing_view() -> None:
    connection = FakeConnection(view_rows=(view_row(),), column_rows=())
    metadata, _ = service(connection)

    assert metadata.list_view_columns(data_source(), "report_patient_results") == ()


def test_base_table_column_rows_are_not_inspected_without_a_view_record() -> None:
    connection = FakeConnection(column_rows=(column_row(),))
    metadata, _ = service(connection)

    with pytest.raises(ViewNotFoundError):
        metadata.list_view_columns(data_source(), "report_patient_results")

    assert len(connection.executions) == 1
    assert "information_schema.VIEWS" in connection.executions[0][0]


def test_column_limit_fails_and_resources_close() -> None:
    connection = FakeConnection(
        view_rows=(view_row(),),
        column_rows=(column_row("one", ordinal=1), column_row("two", ordinal=2)),
    )
    metadata, provider = service(
        connection,
        MetadataAccessPolicy(max_columns_per_view=1),
    )

    with pytest.raises(MetadataLimitExceededError, match="limit of 1"):
        metadata.list_view_columns(data_source(), "report_patient_results")

    assert provider.exit_count == 1
    assert all(cursor.closed for cursor in connection.cursors)


def test_qualified_view_is_rejected_by_default() -> None:
    metadata, _ = service(FakeConnection())

    with pytest.raises(MetadataAccessDeniedError, match="Cross-schema"):
        metadata.get_view(data_source(), "archive.report_patient_results")


def test_cross_schema_requires_and_honors_explicit_allowed_schema() -> None:
    policy = MetadataAccessPolicy(
        allow_cross_schema=True,
        allowed_schemas=("archive",),
    )
    connection = FakeConnection(
        view_rows=(view_row(schema="archive"),),
        column_rows=(column_row(schema="archive"),),
    )
    metadata, _ = service(connection, policy)

    schema = metadata.inspect_view(data_source(), "ARCHIVE.report_patient_results")

    assert schema.view.schema_name == "archive"
    assert connection.executions[0][1] == ("ARCHIVE", "report_patient_results")
    assert connection.executions[1][1] == ("archive", "report_patient_results", 1001)

    with pytest.raises(MetadataAccessDeniedError, match="Cross-schema"):
        metadata.get_view(data_source(), "other.report_patient_results")


def test_system_schema_is_rejected_even_when_cross_schema_is_enabled() -> None:
    policy = MetadataAccessPolicy(
        allow_cross_schema=True,
        allowed_schemas=("mysql",),
    )
    metadata, _ = service(FakeConnection(), policy)

    with pytest.raises(MetadataAccessDeniedError, match="System-schema"):
        metadata.get_view(data_source(), "mysql.user")


@pytest.mark.parametrize(
    "identifier",
    [
        "report patient results",
        "report_view;",
        "report_view -- comment",
        "report_view/*x*/",
        "`report_view`",
        "schema.report.view",
        "../report_view",
        "report$view",
        "",
    ],
)
def test_invalid_view_identifiers_are_rejected_before_querying(identifier: str) -> None:
    connection = FakeConnection()
    metadata, _ = service(connection)

    with pytest.raises(InvalidViewIdentifierError, match="identifier is invalid"):
        metadata.get_view(data_source(), identifier)

    assert connection.executions == []


@pytest.mark.parametrize(
    "identifier",
    ["report_patient_results", "_report_view", "report_view_2026"],
)
def test_valid_unqualified_identifiers_are_accepted(identifier: str) -> None:
    connection = FakeConnection(view_rows=(view_row(identifier),))
    metadata, _ = service(connection)

    assert metadata.get_view(data_source(), identifier).view_name == identifier


def test_configured_database_identifier_is_validated() -> None:
    metadata, _ = service(FakeConnection())

    with pytest.raises(InvalidViewIdentifierError, match="database identifier"):
        metadata.list_views(data_source("lis-reporting"))


@pytest.mark.parametrize(
    "data_type, column_type, expected",
    [
        ("varchar", "varchar(255)", "string"),
        ("TEXT", "TEXT", "string"),
        ("json", "json", "string"),
        ("int", "int(11)", "integer"),
        ("bigint", "bigint unsigned", "integer"),
        ("tinyint", "tinyint(1)", "boolean"),
        ("tinyint", "tinyint(4)", "integer"),
        ("decimal", "decimal(12,2)", "decimal"),
        ("numeric", "numeric(8,3)", "decimal"),
        ("float", "float", "float"),
        ("double", "double", "float"),
        ("bool", "bool", "boolean"),
        ("date", "date", "date"),
        ("time", "time(6)", "time"),
        ("datetime", "datetime(6)", "datetime"),
        ("timestamp", "timestamp", "datetime"),
        ("blob", "blob", "binary"),
        ("varbinary", "varbinary(16)", "binary"),
        ("bit", "bit(1)", "binary"),
        ("geometry", "geometry", "unknown"),
        ("future_type", "future_type(1)", "unknown"),
    ],
)
def test_mysql_type_mapper_is_deterministic(
    data_type: str,
    column_type: str,
    expected: str,
) -> None:
    assert MySQLTypeMapper().normalize(data_type, column_type) == expected


def test_column_conversion_preserves_original_type_and_metadata() -> None:
    connection = FakeConnection(
        view_rows=(view_row(),),
        column_rows=(
            column_row(
                "amount",
                nullable="YES",
                data_type="decimal",
                column_type="decimal(12,2) unsigned",
                default="0.00",
                numeric_precision="12",
                numeric_scale="2",
                datetime_precision=None,
                comment="Invoice amount",
                IGNORED_EXTRA="safe",
            ),
        ),
    )
    metadata, _ = service(connection)

    column = metadata.list_view_columns(data_source(), "report_patient_results")[0]

    assert column == DatabaseColumnInfo(
        name="amount",
        ordinal_position=1,
        database_type="decimal(12,2) unsigned",
        normalized_type="decimal",
        nullable=True,
        default="0.00",
        numeric_precision=12,
        numeric_scale=2,
        column_comment="Invoice amount",
        source_name="amount",
    )


def test_character_length_is_converted_safely() -> None:
    connection = FakeConnection(
        view_rows=(view_row(),),
        column_rows=(
            column_row(
                "patient_name",
                data_type="varchar",
                column_type="varchar(255)",
                character_length="255",
                numeric_precision=None,
                numeric_scale=None,
            ),
        ),
    )
    metadata, _ = service(connection)

    column = metadata.list_view_columns(data_source(), "report_patient_results")[0]

    assert column.character_maximum_length == 255
    assert column.normalized_type == "string"


def test_tuple_rows_are_converted_without_exposing_driver_layout() -> None:
    tuple_view = ("lis", "report_patient_results", "NO", "admin@localhost", "DEFINER")
    tuple_column = (
        "lis",
        "report_patient_results",
        "collected_at",
        1,
        None,
        "NO",
        "datetime",
        "datetime(6)",
        None,
        None,
        None,
        6,
        "Collection time",
        "ignored extra value",
    )
    connection = FakeConnection(view_rows=(tuple_view,), column_rows=(tuple_column,))
    metadata, _ = service(connection)

    column = metadata.inspect_view(data_source(), "report_patient_results").columns[0]

    assert column.normalized_type == "datetime"
    assert column.datetime_precision == 6
    assert column.column_comment == "Collection time"


@pytest.mark.parametrize(
    "bad_row, message",
    [
        ({"TABLE_SCHEMA": "lis"}, "TABLE_NAME"),
        (column_row(ordinal="not-an-int"), "numeric metadata"),
        (column_row(nullable="MAYBE"), "nullable value"),
    ],
)
def test_invalid_metadata_rows_fail_clearly(bad_row: dict[str, object], message: str) -> None:
    if "COLUMN_NAME" in bad_row:
        connection = FakeConnection(view_rows=(view_row(),), column_rows=(bad_row,))
        metadata, _ = service(connection)
        operation = lambda: metadata.list_view_columns(  # noqa: E731
            data_source(), "report_patient_results"
        )
    else:
        connection = FakeConnection(view_rows=(bad_row,))
        metadata, _ = service(connection)
        operation = lambda: metadata.list_views(data_source())  # noqa: E731

    with pytest.raises(MetadataQueryError, match=message):
        operation()


def test_invalid_tuple_row_shape_fails_after_cursor_cleanup() -> None:
    connection = FakeConnection(view_rows=(("lis",),))
    metadata, provider = service(connection)

    with pytest.raises(MetadataQueryError, match="invalid row shape"):
        metadata.list_views(data_source())

    assert provider.exit_count == 1
    assert all(cursor.closed for cursor in connection.cursors)


@pytest.mark.parametrize(
    "error, error_type, message",
    [
        (
            FakeDriverError(1142, "access denied with secret"),
            MetadataAccessDeniedError,
            "cannot read view metadata",
        ),
        (FakeDriverError(1049, "unknown secret"), InvalidDatabaseError, "does not exist"),
        (TimeoutError("timeout secret"), ConnectionTimeoutError, "timed out"),
        (
            FakeDriverError(2013, "connection lost secret"),
            DatabaseUnavailableError,
            "connection was lost",
        ),
        (FakeDriverError(9999, "raw secret"), MetadataQueryError, "metadata query failed"),
    ],
)
def test_metadata_driver_errors_are_mapped_safely_and_cursors_close(
    error: Exception,
    error_type: type[Exception],
    message: str,
) -> None:
    connection = FakeConnection(view_error=error)
    metadata, provider = service(connection)

    with pytest.raises(error_type, match=message) as caught:
        metadata.list_views(data_source())

    assert "secret" not in str(caught.value)
    assert not isinstance(caught.value, FakeDriverError)
    assert provider.exit_count == 1
    assert all(cursor.closed for cursor in connection.cursors)


def test_provider_read_only_failure_propagates_without_metadata_query() -> None:
    connection = FakeConnection()
    metadata, provider = service(
        connection,
        provider_error=ReadOnlySessionError("read-only setup failed"),
    )

    with pytest.raises(ReadOnlySessionError, match="read-only setup failed"):
        metadata.list_views(data_source())

    assert provider.exit_count == 1
    assert connection.executions == []


def test_metadata_service_issues_only_parameterized_information_schema_reads() -> None:
    connection = FakeConnection(
        view_rows=(view_row(),),
        column_rows=(column_row(),),
    )
    metadata, _ = service(connection)

    metadata.inspect_view(data_source(), "report_patient_results")

    for sql, parameters in connection.executions:
        normalized = sql.upper()
        assert (
            "INFORMATION_SCHEMA.VIEWS" in normalized or "INFORMATION_SCHEMA.COLUMNS" in normalized
        )
        assert "REPORT_PATIENT_RESULTS" not in normalized
        assert parameters
        assert "SELECT *" not in normalized
        assert not any(
            keyword in normalized
            for keyword in (" INSERT ", " UPDATE ", " DELETE ", " CREATE ", " DROP ", " ALTER ")
        )


def test_credentials_do_not_appear_in_metadata_logs_or_errors(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "metadata-super-secret"
    connection = FakeConnection(view_error=FakeDriverError(1142, f"denied {secret}"))
    metadata, _ = service(connection)

    with caplog.at_level(logging.INFO):
        with pytest.raises(MetadataAccessDeniedError) as caught:
            metadata.list_views(data_source())

    assert secret not in caplog.text
    assert secret not in str(caught.value)


def test_service_retains_no_connection_or_cursor() -> None:
    connection = FakeConnection(view_rows=(view_row(),))
    metadata, _ = service(connection)

    metadata.list_views(data_source())

    assert not any(
        isinstance(value, (FakeConnection, FakeCursor)) for value in vars(metadata).values()
    )


def test_metadata_models_and_policy_are_immutable() -> None:
    view = DatabaseViewInfo("lis", "report_view")
    column = DatabaseColumnInfo("id", 1, "int", "integer", False)
    schema = DatabaseViewSchema(view, (column,))
    policy = MetadataAccessPolicy(allowed_view_names=["report_view"])  # type: ignore[arg-type]

    assert policy.allowed_view_names == ("report_view",)
    with pytest.raises(FrozenInstanceError):
        view.view_name = "other"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        schema.columns = ()  # type: ignore[misc]


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"max_views": 0}, "max_views"),
        ({"max_columns_per_view": -1}, "max_columns_per_view"),
        ({"allowed_view_names": ("bad name",)}, "invalid identifier"),
        ({"allowed_view_prefixes": ("report-",)}, "invalid identifier"),
        ({"allowed_schemas": ("bad.schema",)}, "invalid identifier"),
        ({"allow_cross_schema": True}, "allowed_schemas"),
        ({"include_system_schemas": "yes"}, "must be a boolean"),
    ],
)
def test_metadata_policy_fails_closed_for_invalid_values(
    kwargs: dict[str, Any],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        MetadataAccessPolicy(**kwargs)


def test_views_only_false_is_explicitly_unsupported() -> None:
    provider = FakeProvider(FakeConnection())

    with pytest.raises(UnsupportedMetadataOperationError, match="views only"):
        MySQLMetadataService(
            provider,  # type: ignore[arg-type]
            policy=MetadataAccessPolicy(views_only=False),
        )


def test_non_mysql_provider_is_rejected() -> None:
    provider = FakeProvider(FakeConnection())
    provider.provider_type = "postgresql"

    with pytest.raises(UnsupportedMetadataOperationError, match="MySQL data-source provider"):
        MySQLMetadataService(provider)  # type: ignore[arg-type]
