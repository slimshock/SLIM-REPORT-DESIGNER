"""Framework-agnostic data-source and dataset management services."""

from .commands import (
    CreateMySQLDataSourceCommand,
    CreateQueryDatasetCommand,
    CreateViewDatasetCommand,
    UpdateMySQLDataSourceCommand,
)
from .errors import (
    DataManagementError,
    DataManagementValidationError,
    DatasetInUseError,
    DatasetNotFoundError,
    DatasetTypeMismatchError,
    DataSourceInUseError,
    DataSourceNotFoundError,
    InvalidDatasetOperationError,
    StaleDiscoveryResultError,
)
from .results import (
    DataManagementResult,
    DatasetConfigurationResult,
    DatasetFieldChangeSummary,
    DatasetSummary,
    DataSourceSummary,
)
from .service import DataSourceManagementService, DesignerDataService

__all__ = [
    "CreateMySQLDataSourceCommand",
    "CreateQueryDatasetCommand",
    "CreateViewDatasetCommand",
    "DataManagementError",
    "DataManagementResult",
    "DataManagementValidationError",
    "DataSourceInUseError",
    "DataSourceManagementService",
    "DataSourceNotFoundError",
    "DataSourceSummary",
    "DatasetConfigurationResult",
    "DatasetFieldChangeSummary",
    "DatasetInUseError",
    "DatasetNotFoundError",
    "DatasetSummary",
    "DatasetTypeMismatchError",
    "DesignerDataService",
    "InvalidDatasetOperationError",
    "StaleDiscoveryResultError",
    "UpdateMySQLDataSourceCommand",
]
