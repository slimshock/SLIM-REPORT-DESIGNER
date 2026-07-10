from __future__ import annotations

import importlib
import logging
from dataclasses import FrozenInstanceError
from types import SimpleNamespace
from typing import Any

import pytest

import slim_report_core
from slim_report_core import (
    AuthenticationError,
    ConnectionTestResult,
    ConnectionTimeoutError,
    CredentialUnavailableError,
    DatabaseUnavailableError,
    DataSourceProviderRegistry,
    DataSourceValidationError,
    DuplicateDataSourceProviderError,
    InvalidDatabaseError,
    MissingDriverError,
    MySQLConnectionConfig,
    MySQLConnectionPolicy,
    MySQLDataSourceProvider,
    ReadOnlySessionError,
    ReportDataSource,
    UnsupportedDataSourceProviderError,
)
from slim_report_core.data_source_providers.mysql import provider as mysql_provider_module

READ_ONLY_COMMAND = "SET SESSION TRANSACTION READ ONLY"
VERIFY_TRANSACTION_READ_ONLY = "SELECT @@session.transaction_read_only"
VERIFY_TX_READ_ONLY = "SELECT @@session.tx_read_only"
HEALTH_CHECK = "SELECT 1"
DATABASE_QUERY = "SELECT DATABASE()"


class FakeDriverError(Exception):
    pass


class FakeCursor:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection
        self.last_query: str | None = None
        self.closed = False

    def execute(self, query: str) -> None:
        self.last_query = query
        self.connection.queries.append(query)
        error = self.connection.query_errors.get(query)
        if error is not None:
            raise error

    def fetchone(self) -> object:
        assert self.last_query is not None
        return self.connection.query_results.get(self.last_query, (1,))

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    def __init__(
        self,
        *,
        query_results: dict[str, object] | None = None,
        query_errors: dict[str, Exception] | None = None,
        server_version: str = "8.0.36",
    ) -> None:
        self.query_results = {
            VERIFY_TRANSACTION_READ_ONLY: (1,),
            HEALTH_CHECK: (1,),
            DATABASE_QUERY: ("lis",),
            **(query_results or {}),
        }
        self.query_errors = query_errors or {}
        self.server_version_text = server_version
        self.queries: list[str] = []
        self.cursors: list[FakeCursor] = []
        self.closed = False
        self.close_count = 0

    def cursor(self) -> FakeCursor:
        cursor = FakeCursor(self)
        self.cursors.append(cursor)
        return cursor

    def close(self) -> None:
        self.closed = True
        self.close_count += 1

    def get_server_info(self) -> str:
        return self.server_version_text


class FailingMetadataConnection(FakeConnection):
    def get_server_info(self) -> str:
        raise FakeDriverError("raw metadata failure with highly-secret")


class FakeDriver:
    def __init__(
        self,
        connection: FakeConnection | None = None,
        error: Exception | None = None,
    ) -> None:
        self.connection = connection or FakeConnection()
        self.error = error
        self.arguments: dict[str, Any] | None = None

    def connect(self, **arguments: Any) -> FakeConnection:
        self.arguments = arguments
        if self.error is not None:
            raise self.error
        return self.connection


class StaticResolver:
    def __init__(self, value: str | None) -> None:
        self.value = value

    def resolve(self, reference: str) -> str | None:
        return self.value


def data_source(**connection_overrides: object) -> ReportDataSource:
    values: dict[str, object] = {
        "host": "db.internal",
        "port": 3306,
        "database": "lis",
        "username": "report_user",
        "password": "runtime-secret",
        "charset": "utf8mb4",
        "connect_timeout": 7,
    }
    values.update(connection_overrides)
    return ReportDataSource(
        id="main_mysql",
        name="Main MySQL",
        type="mysql",
        connection=MySQLConnectionConfig(**values),  # type: ignore[arg-type]
    )


def provider_with_driver(
    monkeypatch: pytest.MonkeyPatch,
    driver: FakeDriver,
    *,
    resolver: StaticResolver | None = None,
    policy: MySQLConnectionPolicy | None = None,
) -> MySQLDataSourceProvider:
    provider = MySQLDataSourceProvider(credential_resolver=resolver, policy=policy)
    monkeypatch.setattr(provider, "_load_driver", lambda: driver)
    return provider


def test_provider_builds_safe_driver_arguments_without_mutating_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = data_source(password=None, password_ref="MYSQL_PASSWORD")
    before = source.connection.to_dict(include_password=True)
    driver = FakeDriver()
    provider = provider_with_driver(monkeypatch, driver, resolver=StaticResolver("resolved-secret"))

    with provider.connection(source):
        pass

    assert driver.arguments == {
        "host": "db.internal",
        "port": 3306,
        "user": "report_user",
        "password": "resolved-secret",
        "database": "lis",
        "charset": "utf8mb4",
        "connect_timeout": 7,
        "autocommit": True,
    }
    assert "client_flag" not in driver.arguments
    assert "local_infile" not in driver.arguments
    assert "multi_statements" not in driver.arguments
    assert source.connection.to_dict(include_password=True) == before


def test_provider_allows_an_intentionally_empty_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = data_source(password="")
    driver = FakeDriver()
    provider = provider_with_driver(monkeypatch, driver)

    with provider.connection(source):
        pass

    assert driver.arguments is not None
    assert driver.arguments["password"] == ""


def test_runtime_password_has_priority_over_resolver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = data_source(password="runtime-secret", password_ref="MYSQL_PASSWORD")
    driver = FakeDriver()
    provider = provider_with_driver(monkeypatch, driver, resolver=StaticResolver("other-secret"))

    with provider.connection(source):
        pass

    assert driver.arguments is not None
    assert driver.arguments["password"] == "runtime-secret"


def test_unresolved_password_reference_raises_safe_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = data_source(password=None, password_ref="UNRESOLVED_MYSQL_PASSWORD")
    monkeypatch.delenv("UNRESOLVED_MYSQL_PASSWORD", raising=False)
    provider = MySQLDataSourceProvider(credential_resolver=StaticResolver(None))

    with pytest.raises(CredentialUnavailableError, match="UNRESOLVED_MYSQL_PASSWORD") as caught:
        provider.create_connection(source)

    assert "runtime-secret" not in str(caught.value)


@pytest.mark.parametrize(
    "field, value, message",
    [
        ("host", "", "host must not be empty"),
        ("port", 0, "port must be between"),
        ("port", 70000, "port must be between"),
        ("database", "", "database must not be empty"),
        ("username", "", "username must not be empty"),
        ("charset", "", "charset must not be empty"),
        ("connect_timeout", 0, "timeout must be at least"),
    ],
)
def test_provider_revalidates_mutated_connection_configuration(
    field: str,
    value: object,
    message: str,
) -> None:
    source = data_source()
    setattr(source.connection, field, value)

    with pytest.raises(DataSourceValidationError, match=message):
        MySQLDataSourceProvider().create_connection(source)


def test_provider_rejects_incompatible_data_source_type() -> None:
    source = data_source()
    source.type = "postgresql"

    with pytest.raises(UnsupportedDataSourceProviderError, match="postgresql"):
        MySQLDataSourceProvider().create_connection(source)


@pytest.mark.parametrize("connection", [None, object()])
def test_provider_rejects_missing_or_wrong_connection_config(connection: object) -> None:
    source = data_source()
    source.connection = connection  # type: ignore[assignment]

    with pytest.raises(DataSourceValidationError, match="valid MySQL connection"):
        MySQLDataSourceProvider().create_connection(source)


def test_provider_rejects_non_report_data_source() -> None:
    with pytest.raises(DataSourceValidationError, match="ReportDataSource"):
        MySQLDataSourceProvider().create_connection(SimpleNamespace(type="mysql"))  # type: ignore[arg-type]


def test_connection_context_closes_after_normal_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = FakeConnection()
    provider = provider_with_driver(monkeypatch, FakeDriver(connection))

    with provider.connection(data_source()) as opened:
        assert opened is connection
        assert not connection.closed
        assert connection.queries[:2] == [READ_ONLY_COMMAND, VERIFY_TRANSACTION_READ_ONLY]

    assert connection.closed
    assert connection.close_count == 1
    assert all(cursor.closed for cursor in connection.cursors)


def test_connection_context_closes_without_swallowing_caller_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = FakeConnection()
    provider = provider_with_driver(monkeypatch, FakeDriver(connection))

    with pytest.raises(RuntimeError, match="caller failed"):
        with provider.connection(data_source()):
            raise RuntimeError("caller failed")

    assert connection.closed
    assert connection.close_count == 1


def test_read_only_setup_failure_closes_connection_and_cursor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = FakeConnection(query_errors={READ_ONLY_COMMAND: FakeDriverError("denied")})
    provider = provider_with_driver(monkeypatch, FakeDriver(connection))

    with pytest.raises(ReadOnlySessionError, match="configured as read-only"):
        with provider.connection(data_source()):
            pass

    assert connection.closed
    assert connection.close_count == 1
    assert all(cursor.closed for cursor in connection.cursors)


def test_provider_does_not_store_live_connections_or_cursors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = provider_with_driver(monkeypatch, FakeDriver())

    with provider.connection(data_source()):
        assert not any(
            isinstance(value, (FakeConnection, FakeCursor)) for value in vars(provider).values()
        )


def test_successful_connection_test_returns_only_safe_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = FakeConnection(server_version="10.4.32-MariaDB")
    driver = FakeDriver(connection)
    provider = provider_with_driver(monkeypatch, driver)

    result = provider.test_connection(data_source(password="highly-secret"))

    assert result == ConnectionTestResult(
        success=True,
        provider="mysql",
        message="MySQL connection succeeded.",
        server_version="10.4.32-MariaDB",
        database="lis",
        elapsed_ms=result.elapsed_ms,
        read_only_verified=True,
    )
    assert result.elapsed_ms is not None and result.elapsed_ms >= 0
    assert "highly-secret" not in repr(result)
    assert connection.queries == [
        READ_ONLY_COMMAND,
        VERIFY_TRANSACTION_READ_ONLY,
        HEALTH_CHECK,
        DATABASE_QUERY,
    ]
    assert connection.closed
    assert all(cursor.closed for cursor in connection.cursors)


@pytest.mark.parametrize(
    "driver_error, message",
    [
        (
            FakeDriverError(1045, "access denied for password highly-secret"),
            "authentication failed",
        ),
        (TimeoutError("timed out with highly-secret"), "timed out"),
        (FakeDriverError(2003, "cannot connect using highly-secret"), "could not be reached"),
        (FakeDriverError(1049, "unknown database highly-secret"), "does not exist"),
    ],
)
def test_connection_test_maps_expected_driver_failures_safely(
    monkeypatch: pytest.MonkeyPatch,
    driver_error: Exception,
    message: str,
) -> None:
    provider = provider_with_driver(monkeypatch, FakeDriver(error=driver_error))

    result = provider.test_connection(data_source(password="highly-secret"))

    assert not result.success
    assert message in result.message
    assert result.elapsed_ms is not None
    assert "highly-secret" not in repr(result)
    assert type(driver_error).__name__ not in result.message


def test_connection_test_maps_server_metadata_errors_and_still_closes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = FailingMetadataConnection()
    provider = provider_with_driver(monkeypatch, FakeDriver(connection))

    result = provider.test_connection(data_source(password="highly-secret"))

    assert not result.success
    assert result.message == "MySQL server metadata could not be read."
    assert "highly-secret" not in repr(result)
    assert connection.closed


@pytest.mark.parametrize(
    "driver_error, error_type",
    [
        (FakeDriverError(1045, "access denied"), AuthenticationError),
        (TimeoutError("timeout"), ConnectionTimeoutError),
        (FakeDriverError(2003, "unreachable"), DatabaseUnavailableError),
        (FakeDriverError(1044, "database denied"), InvalidDatabaseError),
    ],
)
def test_connection_context_raises_project_errors_not_driver_errors(
    monkeypatch: pytest.MonkeyPatch,
    driver_error: Exception,
    error_type: type[Exception],
) -> None:
    provider = provider_with_driver(monkeypatch, FakeDriver(error=driver_error))

    with pytest.raises(error_type):
        with provider.connection(data_source()):
            pass


def test_read_only_verification_falls_back_for_older_mysql_or_mariadb(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = FakeConnection(
        query_errors={VERIFY_TRANSACTION_READ_ONLY: FakeDriverError("unknown variable")},
        query_results={VERIFY_TX_READ_ONLY: (1,)},
    )
    provider = provider_with_driver(monkeypatch, FakeDriver(connection))

    result = provider.test_connection(data_source())

    assert result.success
    assert result.read_only_verified
    assert connection.queries[:3] == [
        READ_ONLY_COMMAND,
        VERIFY_TRANSACTION_READ_ONLY,
        VERIFY_TX_READ_ONLY,
    ]


def test_required_verification_failure_returns_failure_and_closes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = FakeConnection(
        query_errors={
            VERIFY_TRANSACTION_READ_ONLY: FakeDriverError("unknown variable"),
            VERIFY_TX_READ_ONLY: FakeDriverError("unknown variable"),
        }
    )
    provider = provider_with_driver(monkeypatch, FakeDriver(connection))

    result = provider.test_connection(data_source())

    assert not result.success
    assert "could not be verified" in result.message
    assert not result.read_only_verified
    assert connection.closed
    assert HEALTH_CHECK not in connection.queries


def test_policy_can_allow_unverified_read_only_with_deterministic_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = FakeConnection(
        query_errors={
            VERIFY_TRANSACTION_READ_ONLY: FakeDriverError("unknown variable"),
            VERIFY_TX_READ_ONLY: FakeDriverError("unknown variable"),
        }
    )
    policy = MySQLConnectionPolicy(allow_unverified_read_only=True)
    provider = provider_with_driver(monkeypatch, FakeDriver(connection), policy=policy)

    result = provider.test_connection(data_source())

    assert result.success
    assert not result.read_only_verified
    assert result.warnings == ("The MySQL read-only session state could not be verified.",)


def test_server_reported_writable_session_always_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = FakeConnection(query_results={VERIFY_TRANSACTION_READ_ONLY: (0,)})
    policy = MySQLConnectionPolicy(allow_unverified_read_only=True)
    provider = provider_with_driver(monkeypatch, FakeDriver(connection), policy=policy)

    result = provider.test_connection(data_source())

    assert not result.success
    assert not result.read_only_verified
    assert result.message == "The MySQL session is not read-only."
    assert HEALTH_CHECK not in connection.queries


def test_policy_can_skip_verification_without_claiming_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = FakeConnection()
    policy = MySQLConnectionPolicy(verify_read_only_session=False)
    provider = provider_with_driver(monkeypatch, FakeDriver(connection), policy=policy)

    result = provider.test_connection(data_source())

    assert result.success
    assert not result.read_only_verified
    assert result.warnings == ("The MySQL read-only session state was not verified by policy.",)
    assert VERIFY_TRANSACTION_READ_ONLY not in connection.queries


def test_optional_setup_failure_requires_explicit_unverified_permission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = FakeConnection(query_errors={READ_ONLY_COMMAND: FakeDriverError("unsupported")})
    policy = MySQLConnectionPolicy(
        require_read_only_session=False,
        allow_unverified_read_only=True,
    )
    provider = provider_with_driver(monkeypatch, FakeDriver(connection), policy=policy)

    result = provider.test_connection(data_source())

    assert result.success
    assert not result.read_only_verified
    assert result.warnings == ("The MySQL read-only session setting could not be applied.",)


def test_only_approved_internal_sql_is_issued_and_no_dataset_query_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = FakeConnection()
    provider = provider_with_driver(monkeypatch, FakeDriver(connection))
    source = data_source()
    dataset_sql = "SELECT * FROM private_patient_records"

    result = provider.test_connection(source)

    assert result.success
    assert dataset_sql not in connection.queries
    assert set(connection.queries) <= {
        READ_ONLY_COMMAND,
        VERIFY_TRANSACTION_READ_ONLY,
        VERIFY_TX_READ_ONLY,
        HEALTH_CHECK,
        DATABASE_QUERY,
    }
    assert not any(
        query.upper().startswith(("INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER"))
        for query in connection.queries
    )


def test_missing_driver_is_lazy_and_raises_focused_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing_import(name: str) -> object:
        raise ModuleNotFoundError("No module named 'pymysql'", name="pymysql")

    monkeypatch.setattr(mysql_provider_module, "import_module", missing_import)

    with pytest.raises(MissingDriverError, match=r"slim-report-core\[mysql\]"):
        MySQLDataSourceProvider().create_connection(data_source())


def test_importing_core_does_not_load_optional_driver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        mysql_provider_module,
        "import_module",
        lambda name: calls.append(name),
    )

    importlib.reload(slim_report_core)

    assert calls == []
    assert slim_report_core.MySQLDataSourceProvider is MySQLDataSourceProvider


def test_password_never_appears_in_provider_logs(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "never-log-this-password"
    provider = provider_with_driver(
        monkeypatch,
        FakeDriver(error=FakeDriverError(1045, f"access denied for {secret}")),
    )

    with caplog.at_level(logging.INFO):
        result = provider.test_connection(data_source(password=secret))

    assert not result.success
    assert secret not in caplog.text
    assert secret not in result.message


def test_connection_result_and_policy_are_immutable() -> None:
    result = ConnectionTestResult(success=True, provider="mysql", message="ok")
    policy = MySQLConnectionPolicy()

    with pytest.raises(FrozenInstanceError):
        result.success = False  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        policy.require_read_only_session = False  # type: ignore[misc]


def test_registry_is_case_insensitive_and_deterministic() -> None:
    registry = DataSourceProviderRegistry()
    mysql = MySQLDataSourceProvider()
    postgres = SimpleNamespace(provider_type="PostgreSQL")

    registry.register(postgres)  # type: ignore[arg-type]
    registry.register(mysql)

    assert registry.get("MYSQL") is mysql
    assert registry.get("postgresql") is postgres
    assert registry.has("MySql")
    assert registry.available() == ("mysql", "postgresql")


def test_registry_rejects_duplicates_unless_replacement_is_explicit() -> None:
    registry = DataSourceProviderRegistry()
    first = MySQLDataSourceProvider()
    replacement = MySQLDataSourceProvider()
    registry.register(first)

    with pytest.raises(DuplicateDataSourceProviderError, match="already registered"):
        registry.register(replacement)

    registry.register(replacement, replace=True)
    assert registry.get("mysql") is replacement


def test_registry_unregisters_and_rejects_unknown_types() -> None:
    registry = DataSourceProviderRegistry()
    registry.register(MySQLDataSourceProvider())

    registry.unregister("MYSQL")

    assert not registry.has("mysql")
    with pytest.raises(UnsupportedDataSourceProviderError, match="must not be empty"):
        registry.get(" ")
    with pytest.raises(UnsupportedDataSourceProviderError, match="No data-source provider"):
        registry.get("oracle")
    with pytest.raises(UnsupportedDataSourceProviderError, match="No data-source provider"):
        registry.unregister("mysql")
