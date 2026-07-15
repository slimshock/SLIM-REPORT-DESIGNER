"""Secure, lazy-loaded PyMySQL data-source provider."""

from __future__ import annotations

import logging
import socket
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from importlib import import_module
from time import monotonic
from typing import TYPE_CHECKING, Any

from ...data_sources import (
    MYSQL_DATA_SOURCE_TYPE,
    CredentialResolver,
    MySQLConnectionConfig,
    ReportDataSource,
)
from ...exceptions import CredentialResolutionError, DataSourceValidationError
from ..base import ConnectionTestResult
from ..errors import (
    AuthenticationError,
    ConnectionTimeoutError,
    CredentialUnavailableError,
    DatabaseUnavailableError,
    InvalidDatabaseError,
    MissingDriverError,
    ReadOnlySessionError,
    UnsupportedDataSourceProviderError,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ...dataset_execution.provider import (
        ProviderDatasetExecutionRequest,
        ProviderDatasetRowStream,
    )
    from ...query_discovery import ProviderFieldDiscoveryResult, QueryFieldDiscoveryPolicy

_READ_ONLY_COMMAND = "SET SESSION TRANSACTION READ ONLY"
_READ_ONLY_VERIFICATION_QUERIES = (
    "SELECT @@session.transaction_read_only",
    "SELECT @@session.tx_read_only",
)
_HEALTH_CHECK_QUERY = "SELECT 1"
_DATABASE_QUERY = "SELECT DATABASE()"


@dataclass(frozen=True)
class MySQLConnectionPolicy:
    """Policy for read-only setup and verification of MySQL connections."""

    require_read_only_session: bool = True
    verify_read_only_session: bool = True
    allow_unverified_read_only: bool = False


@dataclass(frozen=True)
class _ReadOnlyStatus:
    verified: bool
    warnings: tuple[str, ...] = ()


class MySQLDataSourceProvider:
    """Create and test isolated read-only MySQL-compatible connections."""

    provider_type = MYSQL_DATA_SOURCE_TYPE
    dialect_name = "mysql"

    def __init__(
        self,
        credential_resolver: CredentialResolver | None = None,
        policy: MySQLConnectionPolicy | None = None,
    ) -> None:
        self._credential_resolver = credential_resolver
        self.policy = policy or MySQLConnectionPolicy()

    @contextmanager
    def connection(self, data_source: ReportDataSource) -> Iterator[object]:
        """Yield one configured connection and always close it afterward."""
        connection, _ = self._open_configured_connection(data_source)
        try:
            yield connection
        finally:
            self.close_connection(connection)

    def create_connection(self, data_source: ReportDataSource) -> object:
        """Open a new autocommit connection using safe keyword arguments."""
        config = self._validate_data_source(data_source)
        password = self._resolve_password(config)
        driver = self._load_driver()
        arguments = self._connection_arguments(config, password)
        try:
            return driver.connect(**arguments)
        except Exception as exc:
            raise self._map_connection_error(exc) from exc

    def configure_read_only_session(self, connection: object) -> tuple[str, ...]:
        """Apply the MySQL transaction read-only session characteristic."""
        cursor = None
        try:
            cursor = connection.cursor()  # type: ignore[attr-defined]
            cursor.execute(_READ_ONLY_COMMAND)
        except Exception as exc:
            raise ReadOnlySessionError(
                "The MySQL session could not be configured as read-only."
            ) from exc
        finally:
            self._close_cursor(cursor)
        return (_READ_ONLY_COMMAND,)

    def verify_read_only_session(self, connection: object) -> bool:
        """Verify MySQL or MariaDB session state using compatible variable names."""
        for query in _READ_ONLY_VERIFICATION_QUERIES:
            cursor = None
            try:
                cursor = connection.cursor()  # type: ignore[attr-defined]
                cursor.execute(query)
                row = cursor.fetchone()
                return self._read_only_value(row)
            except Exception:
                continue
            finally:
                self._close_cursor(cursor)
        raise ReadOnlySessionError("The MySQL read-only session state could not be verified.")

    def close_connection(self, connection: object) -> None:
        """Close a driver connection without leaking cleanup errors."""
        try:
            connection.close()  # type: ignore[attr-defined]
        except Exception:
            logger.warning("A MySQL connection could not be closed cleanly.")

    def test_connection(self, data_source: ReportDataSource) -> ConnectionTestResult:
        """Run only read-only setup, verification, and minimal health metadata checks."""
        self._validate_data_source(data_source)
        started = monotonic()
        logger.info("MySQL connection test started.")
        connection: object | None = None
        try:
            connection, read_only = self._open_configured_connection(data_source)
            database = self._health_check(connection)
            server_version = self._server_version(connection)
            elapsed_ms = self._elapsed_ms(started)
            logger.info(
                "MySQL connection test succeeded in %.3f ms; read-only verified=%s.",
                elapsed_ms,
                read_only.verified,
            )
            return ConnectionTestResult(
                success=True,
                provider=self.provider_type,
                message="MySQL connection succeeded.",
                server_version=server_version,
                database=database,
                elapsed_ms=elapsed_ms,
                read_only_verified=read_only.verified,
                warnings=read_only.warnings,
            )
        except MissingDriverError:
            raise
        except CredentialUnavailableError:
            raise
        except (
            AuthenticationError,
            ConnectionTimeoutError,
            DatabaseUnavailableError,
            InvalidDatabaseError,
            ReadOnlySessionError,
        ) as exc:
            elapsed_ms = self._elapsed_ms(started)
            logger.warning("MySQL connection test failed in %.3f ms: %s", elapsed_ms, exc)
            return ConnectionTestResult(
                success=False,
                provider=self.provider_type,
                message=str(exc),
                elapsed_ms=elapsed_ms,
            )
        finally:
            if connection is not None:
                self.close_connection(connection)

    def discover_query_fields(
        self,
        *,
        data_source: ReportDataSource,
        sql: str,
        parameters: Mapping[str, object],
        policy: QueryFieldDiscoveryPolicy,
    ) -> ProviderFieldDiscoveryResult:
        """Discover fields for one already validated SELECT query."""
        from .discovery import MySQLQueryFieldDiscovery

        return MySQLQueryFieldDiscovery(self).discover_query_fields(
            data_source=data_source,
            sql=sql,
            parameters=parameters,
            policy=policy,
        )

    def open_dataset_stream(
        self,
        request: ProviderDatasetExecutionRequest,
    ) -> ProviderDatasetRowStream:
        """Open one unbuffered read-only dataset stream."""
        from .execution import MySQLProviderDatasetRowStream

        return MySQLProviderDatasetRowStream.open(self, request)

    def _open_configured_connection(
        self,
        data_source: ReportDataSource,
    ) -> tuple[object, _ReadOnlyStatus]:
        connection = self.create_connection(data_source)
        try:
            status = self._configure_and_verify(connection)
        except Exception:
            self.close_connection(connection)
            raise
        return connection, status

    def _configure_and_verify(self, connection: object) -> _ReadOnlyStatus:
        warnings: list[str] = []
        configured = False
        try:
            self.configure_read_only_session(connection)
            configured = True
        except ReadOnlySessionError:
            if self.policy.require_read_only_session:
                raise
            if self.policy.verify_read_only_session and not self.policy.allow_unverified_read_only:
                raise
            warnings.append("The MySQL read-only session setting could not be applied.")

        if not configured:
            return _ReadOnlyStatus(verified=False, warnings=tuple(warnings))
        if not self.policy.verify_read_only_session:
            warnings.append("The MySQL read-only session state was not verified by policy.")
            return _ReadOnlyStatus(verified=False, warnings=tuple(warnings))

        try:
            verified = self.verify_read_only_session(connection)
        except ReadOnlySessionError:
            if not self.policy.allow_unverified_read_only:
                raise
            warnings.append("The MySQL read-only session state could not be verified.")
            return _ReadOnlyStatus(verified=False, warnings=tuple(warnings))

        if not verified:
            raise ReadOnlySessionError("The MySQL session is not read-only.")
        return _ReadOnlyStatus(verified=verified, warnings=tuple(warnings))

    def _validate_data_source(self, data_source: ReportDataSource) -> MySQLConnectionConfig:
        if not isinstance(data_source, ReportDataSource):
            raise DataSourceValidationError(
                "The MySQL provider requires a ReportDataSource instance."
            )
        if str(data_source.type).lower() != self.provider_type:
            raise UnsupportedDataSourceProviderError(
                f"The data source type {data_source.type!r} is not supported by the MySQL provider."
            )
        config = data_source.connection
        if not isinstance(config, MySQLConnectionConfig):
            raise DataSourceValidationError(
                "The MySQL data source does not contain a valid MySQL connection configuration."
            )
        if not isinstance(config.host, str) or not config.host.strip():
            raise DataSourceValidationError("The MySQL host must not be empty.")
        if (
            isinstance(config.port, bool)
            or not isinstance(config.port, int)
            or not 1 <= config.port <= 65535
        ):
            raise DataSourceValidationError(
                "connection.port must be an integer between 1 and 65535."
            )
        if not isinstance(config.database, str) or not config.database.strip():
            raise DataSourceValidationError("The MySQL database must not be empty.")
        if not isinstance(config.username, str) or not config.username.strip():
            raise DataSourceValidationError("The MySQL username must not be empty.")
        if not isinstance(config.charset, str) or not config.charset.strip():
            raise DataSourceValidationError("The MySQL charset must not be empty.")
        if (
            isinstance(config.connect_timeout, bool)
            or not isinstance(config.connect_timeout, int)
            or config.connect_timeout < 1
        ):
            raise DataSourceValidationError("connection.connectTimeout must be a positive integer.")
        if (
            isinstance(config.query_timeout, bool)
            or not isinstance(config.query_timeout, int)
            or config.query_timeout < 1
        ):
            raise DataSourceValidationError("connection.queryTimeout must be a positive integer.")
        if config.password_ref is not None and (
            not isinstance(config.password_ref, str) or not config.password_ref.strip()
        ):
            raise DataSourceValidationError("The MySQL credential reference is invalid.")
        return config

    def _resolve_password(self, config: MySQLConnectionConfig) -> str:
        try:
            password = config.resolve_password(self._credential_resolver)
        except CredentialResolutionError as exc:
            raise CredentialUnavailableError(
                "The configured MySQL credential could not be resolved."
            ) from exc
        if password is None and config.password_ref is not None:
            raise CredentialUnavailableError(
                "The configured MySQL credential could not be resolved."
            )
        return password if password is not None else ""

    @staticmethod
    def _connection_arguments(config: MySQLConnectionConfig, password: str) -> dict[str, Any]:
        return {
            "host": config.host,
            "port": config.port,
            "user": config.username,
            "password": password,
            "database": config.database,
            "charset": config.charset,
            "connect_timeout": config.connect_timeout,
            "read_timeout": config.query_timeout,
            "write_timeout": config.query_timeout,
            "autocommit": True,
        }

    @staticmethod
    def _load_driver() -> Any:
        try:
            return import_module("pymysql")
        except ImportError as exc:
            raise MissingDriverError(
                "MySQL support requires the optional 'mysql' dependency. "
                "Install it with: pip install slim-report-core[mysql]"
            ) from exc

    @staticmethod
    def _map_connection_error(exc: Exception) -> Exception:
        code = exc.args[0] if exc.args and isinstance(exc.args[0], int) else None
        if isinstance(exc, (TimeoutError, socket.timeout)) or MySQLDataSourceProvider._is_timeout(
            exc
        ):
            return ConnectionTimeoutError("The MySQL connection timed out.")
        if code == 1045:
            return AuthenticationError("MySQL authentication failed.")
        if code in {1044, 1049}:
            return InvalidDatabaseError(
                "The configured database does not exist or is not accessible."
            )
        if code in {2002, 2003, 2005, 2006, 2013}:
            return DatabaseUnavailableError("The MySQL server could not be reached.")
        return DatabaseUnavailableError("The MySQL connection could not be established.")

    @staticmethod
    def _is_timeout(exc: BaseException) -> bool:
        current: BaseException | None = exc
        seen: set[int] = set()
        while current is not None and id(current) not in seen:
            if isinstance(current, (TimeoutError, socket.timeout)):
                return True
            if "timed out" in str(current).lower() or "timeout" in str(current).lower():
                return True
            seen.add(id(current))
            current = current.__cause__ or current.__context__
        return False

    def _health_check(self, connection: object) -> str | None:
        cursor = None
        try:
            cursor = connection.cursor()  # type: ignore[attr-defined]
            cursor.execute(_HEALTH_CHECK_QUERY)
            cursor.fetchone()
            cursor.execute(_DATABASE_QUERY)
            database = self._row_value(cursor.fetchone())
            return str(database) if database is not None else None
        except Exception as exc:
            mapped = self._map_connection_error(exc)
            raise mapped from exc
        finally:
            self._close_cursor(cursor)

    @staticmethod
    def _server_version(connection: object) -> str | None:
        try:
            getter = getattr(connection, "get_server_info", None)
            if callable(getter):
                value = getter()
                return str(value) if value is not None else None
            value = getattr(connection, "server_version", None)
            return str(value) if value is not None else None
        except Exception as exc:
            raise DatabaseUnavailableError("MySQL server metadata could not be read.") from exc

    @staticmethod
    def _read_only_value(row: object) -> bool:
        value = MySQLDataSourceProvider._row_value(row)
        if isinstance(value, str):
            return value.strip().upper() in {"1", "ON", "TRUE", "YES"}
        return bool(value)

    @staticmethod
    def _row_value(row: object) -> Any:
        if isinstance(row, Mapping):
            return next(iter(row.values()), None)
        if isinstance(row, (tuple, list)):
            return row[0] if row else None
        return row

    @staticmethod
    def _close_cursor(cursor: object | None) -> None:
        if cursor is None:
            return
        try:
            cursor.close()  # type: ignore[attr-defined]
        except Exception:
            logger.warning("A MySQL cursor could not be closed cleanly.")

    @staticmethod
    def _elapsed_ms(started: float) -> float:
        return max(0.0, (monotonic() - started) * 1000.0)
