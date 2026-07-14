"""Focused exceptions for safe query field discovery."""

from __future__ import annotations

from ..exceptions import DataSourceError


class QueryFieldDiscoveryError(DataSourceError):
    """Base exception for query field discovery failures."""


class QueryValidationFailedError(QueryFieldDiscoveryError):
    """Raised when a dataset query does not pass SQL validation."""


class QueryParameterError(QueryFieldDiscoveryError):
    """Raised when discovery query parameters are invalid."""


class MissingQueryParameterValueError(QueryParameterError):
    """Raised when a required query parameter has no discovery value."""


class InvalidQueryParameterValueError(QueryParameterError):
    """Raised when a query parameter value cannot be converted safely."""


class QueryExecutionError(QueryFieldDiscoveryError):
    """Raised when a query cannot be executed for field discovery."""


class QueryExecutionTimeoutError(QueryExecutionError):
    """Raised when a query field discovery operation times out."""


class QueryReturnedNoColumnsError(QueryFieldDiscoveryError):
    """Raised when cursor metadata contains no returned columns."""


class DuplicateOutputColumnError(QueryFieldDiscoveryError):
    """Raised when a query returns duplicate output column names."""


class TooManyOutputColumnsError(QueryFieldDiscoveryError):
    """Raised when returned column metadata exceeds policy limits."""


class UnsupportedDiscoveredTypeError(QueryFieldDiscoveryError):
    """Raised when policy forbids an unknown discovered database type."""
