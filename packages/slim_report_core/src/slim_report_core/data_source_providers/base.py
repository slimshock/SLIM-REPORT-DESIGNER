"""Framework-independent data-source provider contracts."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Protocol

from ..data_sources import ReportDataSource


@dataclass(frozen=True)
class ConnectionTestResult:
    """Safe, immutable outcome of a minimal provider connection test."""

    success: bool
    provider: str
    message: str
    server_version: str | None = None
    database: str | None = None
    elapsed_ms: float | None = None
    read_only_verified: bool = False
    warnings: tuple[str, ...] = ()


class DataSourceProvider(Protocol):
    """Minimal contract shared by SQL and future non-SQL providers."""

    provider_type: str

    def test_connection(self, data_source: ReportDataSource) -> ConnectionTestResult:
        """Test provider connectivity without running application queries."""
        ...

    def connection(self, data_source: ReportDataSource) -> AbstractContextManager[object]:
        """Return context-managed access to a newly owned connection."""
        ...


class SQLDataSourceProvider(DataSourceProvider, Protocol):
    """Additional lifecycle operations implemented only by SQL providers."""

    dialect_name: str

    def create_connection(self, data_source: ReportDataSource) -> object:
        """Create a new driver connection for a compatible data source."""
        ...

    def configure_read_only_session(self, connection: object) -> tuple[str, ...]:
        """Configure a new connection before it is exposed to callers."""
        ...

    def close_connection(self, connection: object) -> None:
        """Close one connection owned by the current operation."""
        ...
