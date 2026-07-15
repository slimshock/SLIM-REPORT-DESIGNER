"""Focused exceptions for report data-source and dataset management."""

from __future__ import annotations

from ..exceptions import DataSourceError


class DataManagementError(DataSourceError):
    """Base exception for management-service failures."""


class DataSourceNotFoundError(DataManagementError):
    """Raised when a requested report data source is missing."""


class DatasetNotFoundError(DataManagementError):
    """Raised when a requested report dataset is missing."""


class DatasetInUseError(DataManagementError):
    """Raised when a dataset is referenced by report bindings."""


class DataSourceInUseError(DataManagementError):
    """Raised when a data source has dependent datasets."""


class InvalidDatasetOperationError(DataManagementError):
    """Raised when a dataset operation is invalid for the current model."""


class DatasetTypeMismatchError(InvalidDatasetOperationError):
    """Raised when an operation targets the wrong dataset source type."""


class StaleDiscoveryResultError(DataManagementError):
    """Raised when discovered fields do not match the target dataset."""


class DataManagementValidationError(DataManagementError):
    """Raised when a management command is structurally invalid."""
