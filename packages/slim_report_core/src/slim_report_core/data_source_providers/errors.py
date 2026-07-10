"""Focused exceptions for data-source provider operations."""

from ..exceptions import DataSourceError


class DataSourceProviderError(DataSourceError):
    """Base exception for provider registration and lookup failures."""


class DataSourceConnectionError(DataSourceError):
    """Base exception for safe connection failures."""


class UnsupportedDataSourceProviderError(DataSourceProviderError):
    """Raised when no compatible provider is available."""


class DuplicateDataSourceProviderError(DataSourceProviderError):
    """Raised when a provider type is registered more than once."""


class CredentialUnavailableError(DataSourceConnectionError):
    """Raised when a configured credential reference cannot be resolved."""


class ConnectionTimeoutError(DataSourceConnectionError):
    """Raised when opening or checking a connection times out."""


class AuthenticationError(DataSourceConnectionError):
    """Raised when database authentication fails."""


class DatabaseUnavailableError(DataSourceConnectionError):
    """Raised when the configured database server cannot be reached."""


class InvalidDatabaseError(DataSourceConnectionError):
    """Raised when a database does not exist or is inaccessible."""


class ReadOnlySessionError(DataSourceConnectionError):
    """Raised when a connection cannot be made safely read-only."""


class MissingDriverError(DataSourceConnectionError):
    """Raised when an optional database driver is unavailable."""
