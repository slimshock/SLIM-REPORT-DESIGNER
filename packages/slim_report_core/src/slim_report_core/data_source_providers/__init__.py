"""Public data-source provider contracts and implementations."""

from .base import ConnectionTestResult, DataSourceProvider, SQLDataSourceProvider
from .errors import (
    AuthenticationError,
    ConnectionTimeoutError,
    CredentialUnavailableError,
    DatabaseUnavailableError,
    DataSourceConnectionError,
    DataSourceMetadataError,
    DataSourceProviderError,
    DuplicateDataSourceProviderError,
    InvalidDatabaseError,
    InvalidViewIdentifierError,
    MetadataAccessDeniedError,
    MetadataLimitExceededError,
    MetadataQueryError,
    MissingDriverError,
    ReadOnlySessionError,
    UnsupportedDataSourceProviderError,
    UnsupportedMetadataOperationError,
    ViewNotFoundError,
)
from .metadata import (
    DatabaseColumnInfo,
    DatabaseViewInfo,
    DatabaseViewSchema,
    MetadataAccessPolicy,
)
from .mysql import (
    MySQLConnectionPolicy,
    MySQLDataSourceProvider,
    MySQLMetadataService,
    MySQLTypeMapper,
)
from .registry import DataSourceProviderRegistry

__all__ = [
    "AuthenticationError",
    "ConnectionTestResult",
    "ConnectionTimeoutError",
    "CredentialUnavailableError",
    "DataSourceConnectionError",
    "DataSourceMetadataError",
    "DataSourceProvider",
    "DataSourceProviderError",
    "DataSourceProviderRegistry",
    "DatabaseColumnInfo",
    "DatabaseUnavailableError",
    "DatabaseViewInfo",
    "DatabaseViewSchema",
    "DuplicateDataSourceProviderError",
    "InvalidDatabaseError",
    "InvalidViewIdentifierError",
    "MetadataAccessDeniedError",
    "MetadataAccessPolicy",
    "MetadataLimitExceededError",
    "MetadataQueryError",
    "MissingDriverError",
    "MySQLConnectionPolicy",
    "MySQLDataSourceProvider",
    "MySQLMetadataService",
    "MySQLTypeMapper",
    "ReadOnlySessionError",
    "SQLDataSourceProvider",
    "UnsupportedDataSourceProviderError",
    "UnsupportedMetadataOperationError",
    "ViewNotFoundError",
]
