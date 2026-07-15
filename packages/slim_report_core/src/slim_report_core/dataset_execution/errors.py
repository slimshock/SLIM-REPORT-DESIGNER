"""Safe errors raised by bounded dataset execution."""

from __future__ import annotations

from ..exceptions import ReportValidationError


class DatasetExecutionError(ReportValidationError):
    """Base error for runtime dataset execution."""

    code = "dataset_execution_error"


class DatasetNotExecutableError(DatasetExecutionError):
    """Raised when stored dataset metadata cannot be executed."""

    code = "dataset_not_executable"


class DatasetExecutionProviderError(DatasetExecutionError):
    """Raised when the provider cannot safely execute a dataset."""

    code = "dataset_provider_error"


class DatasetSchemaMismatchError(DatasetExecutionError):
    """Raised when returned columns differ from stored dataset fields."""

    code = "dataset_schema_mismatch"


class DatasetRowShapeError(DatasetExecutionError):
    """Raised when a driver row does not match the validated schema."""

    code = "dataset_row_shape"


class DatasetExecutionTimeoutError(DatasetExecutionError):
    """Raised when database I/O exceeds the effective runtime timeout."""

    code = "dataset_execution_timeout"


class DatasetExecutionCancelledError(DatasetExecutionError):
    """Raised when an execution-specific cancellation token is cancelled."""

    code = "dataset_execution_cancelled"


class DatasetResultLimitError(DatasetExecutionError):
    """Raised when a cell or total result-size limit is exceeded."""

    code = "dataset_result_limit"


class DatasetValueTypeError(DatasetExecutionError):
    """Raised when a driver value type is not approved by policy."""

    code = "dataset_value_type"


class DatasetExecutionConfigurationError(DatasetExecutionError):
    """Raised when execution options exceed configured security limits."""

    code = "dataset_execution_configuration"
