"""Safe metadata-only field discovery for query-backed datasets."""

from .errors import (
    DuplicateOutputColumnError,
    InvalidQueryParameterValueError,
    MissingQueryParameterValueError,
    QueryExecutionError,
    QueryExecutionTimeoutError,
    QueryFieldDiscoveryError,
    QueryParameterError,
    QueryReturnedNoColumnsError,
    QueryValidationFailedError,
    TooManyOutputColumnsError,
    UnsupportedDiscoveredTypeError,
)
from .models import (
    DiscoveredColumn,
    ProviderFieldDiscoveryResult,
    QueryFieldDiscoveryResult,
)
from .parameters import QueryParameterValueConverter
from .policy import QueryFieldDiscoveryPolicy
from .service import QueryFieldDiscoveryProvider, QueryFieldDiscoveryService

__all__ = [
    "DiscoveredColumn",
    "DuplicateOutputColumnError",
    "InvalidQueryParameterValueError",
    "MissingQueryParameterValueError",
    "ProviderFieldDiscoveryResult",
    "QueryExecutionError",
    "QueryExecutionTimeoutError",
    "QueryFieldDiscoveryError",
    "QueryFieldDiscoveryPolicy",
    "QueryFieldDiscoveryProvider",
    "QueryFieldDiscoveryResult",
    "QueryFieldDiscoveryService",
    "QueryParameterError",
    "QueryParameterValueConverter",
    "QueryReturnedNoColumnsError",
    "QueryValidationFailedError",
    "TooManyOutputColumnsError",
    "UnsupportedDiscoveredTypeError",
]
