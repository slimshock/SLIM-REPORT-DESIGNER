"""Public data-source provider contracts and implementations."""

from .base import ConnectionTestResult, DataSourceProvider, SQLDataSourceProvider
from .errors import (
    AuthenticationError,
    ConnectionTimeoutError,
    CredentialUnavailableError,
    DatabaseUnavailableError,
    DataSourceConnectionError,
    DataSourceProviderError,
    DuplicateDataSourceProviderError,
    InvalidDatabaseError,
    MissingDriverError,
    ReadOnlySessionError,
    UnsupportedDataSourceProviderError,
)
from .mysql import MySQLConnectionPolicy, MySQLDataSourceProvider
from .registry import DataSourceProviderRegistry

__all__ = [
    "AuthenticationError",
    "ConnectionTestResult",
    "ConnectionTimeoutError",
    "CredentialUnavailableError",
    "DataSourceConnectionError",
    "DataSourceProvider",
    "DataSourceProviderError",
    "DataSourceProviderRegistry",
    "DatabaseUnavailableError",
    "DuplicateDataSourceProviderError",
    "InvalidDatabaseError",
    "MissingDriverError",
    "MySQLConnectionPolicy",
    "MySQLDataSourceProvider",
    "ReadOnlySessionError",
    "SQLDataSourceProvider",
    "UnsupportedDataSourceProviderError",
]
