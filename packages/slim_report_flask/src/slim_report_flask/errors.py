"""Central credential-safe Flask error mapping."""

from __future__ import annotations

from dataclasses import dataclass

from slim_report_core import (
    AuthenticationError,
    ConnectionTimeoutError,
    CredentialUnavailableError,
    DatabaseUnavailableError,
    DatasetExecutionCancelledError,
    DatasetExecutionProviderError,
    DatasetExecutionTimeoutError,
    DatasetNotExecutableError,
    DatasetNotFoundError,
    DatasetResultLimitError,
    DatasetSchemaMismatchError,
    DataSourceConnectionError,
    DataSourceMetadataError,
    DataSourceNotFoundError,
    DataSourceValidationError,
    InvalidSQLParameterError,
    InvalidViewIdentifierError,
    MetadataAccessDeniedError,
    MetadataLimitExceededError,
    MetadataQueryError,
    MissingDriverError,
    MultipleStatementsError,
    QueryExecutionError,
    QueryExecutionTimeoutError,
    QueryFieldDiscoveryError,
    ReadOnlySessionError,
    RuntimeBandConfigurationError,
    RuntimeBindingResolutionError,
    RuntimeDatasetSelectionError,
    RuntimeParameterDatasetError,
    RuntimeParameterError,
    RuntimePreviewCancelledError,
    RuntimePreviewTimeoutError,
    RuntimeReportLimitError,
    RuntimeReportRenderError,
    RuntimeUnsupportedBindingError,
    SlimReportError,
    SQLValidationError,
    UnsafeSQLConstructError,
    ViewNotFoundError,
)
from slim_report_core.assets import (
    AssetError,
    AssetIdError,
    AssetNotFoundError,
    AssetPermissionError,
    AssetStorageError,
    AssetTypeError,
)
from slim_report_core.exceptions import ReportSerializationError
from slim_report_core.storage import (
    TemplateIdError,
    TemplateNotFoundError,
    TemplatePermissionError,
    TemplateStorageError,
    TemplateValidationError,
)


@dataclass(frozen=True)
class SafeError:
    """Stable public error metadata with no raw exception content."""

    code: str
    message: str
    status: int
    details: tuple[dict[str, str], ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "details": list(self.details),
        }


_MAPPINGS: tuple[tuple[type[BaseException], SafeError], ...] = (
    (
        CredentialUnavailableError,
        SafeError(
            "credential_unavailable", "The configured MySQL credential could not be resolved.", 503
        ),
    ),
    (MissingDriverError, SafeError("driver_missing", "The MySQL driver is not installed.", 503)),
    (AuthenticationError, SafeError("authentication_failed", "MySQL authentication failed.", 503)),
    (
        DatabaseUnavailableError,
        SafeError("database_unavailable", "The configured MySQL database is unavailable.", 503),
    ),
    (
        ConnectionTimeoutError,
        SafeError("data_source_timeout", "The MySQL connection timed out.", 504),
    ),
    (
        ReadOnlySessionError,
        SafeError("read_only_failed", "The MySQL read-only session could not be verified.", 503),
    ),
    (
        DataSourceConnectionError,
        SafeError("database_unavailable", "The configured MySQL database is unavailable.", 503),
    ),
    (
        DataSourceNotFoundError,
        SafeError("data_source_not_found", "The requested data source was not found.", 404),
    ),
    (
        DataSourceValidationError,
        SafeError("data_source_invalid", "The data-source configuration is invalid.", 400),
    ),
    (
        MetadataAccessDeniedError,
        SafeError("metadata_access_denied", "Metadata access is not allowed.", 403),
    ),
    (
        InvalidViewIdentifierError,
        SafeError("invalid_identifier", "The reporting view identifier is invalid.", 400),
    ),
    (
        ViewNotFoundError,
        SafeError("view_not_found", "The configured reporting view is not available.", 404),
    ),
    (
        MetadataLimitExceededError,
        SafeError(
            "metadata_limit_exceeded", "The metadata result exceeded the configured limit.", 400
        ),
    ),
    (
        MetadataQueryError,
        SafeError("metadata_unavailable", "Reporting metadata could not be read.", 503),
    ),
    (
        DataSourceMetadataError,
        SafeError("metadata_unavailable", "Reporting metadata could not be read.", 503),
    ),
    (
        MultipleStatementsError,
        SafeError(
            "sql_multiple_statements", "SQL must contain exactly one read-only statement.", 400
        ),
    ),
    (
        InvalidSQLParameterError,
        SafeError(
            "sql_invalid_parameter_style", "The query parameter configuration is invalid.", 400
        ),
    ),
    (
        UnsafeSQLConstructError,
        SafeError("sql_unsafe", "The query contains a disallowed SQL construct.", 400),
    ),
    (SQLValidationError, SafeError("sql_invalid", "The read-only query is invalid.", 400)),
    (
        DatasetNotFoundError,
        SafeError("dataset_not_found", "The requested dataset was not found.", 404),
    ),
    (
        DatasetSchemaMismatchError,
        SafeError(
            "dataset_schema_mismatch",
            "The query result no longer matches the stored dataset fields.",
            400,
        ),
    ),
    (
        DatasetResultLimitError,
        SafeError("dataset_limit_exceeded", "The dataset exceeded a configured result limit.", 400),
    ),
    (
        DatasetExecutionCancelledError,
        SafeError("dataset_cancelled", "Dataset execution was cancelled.", 409),
    ),
    (
        DatasetExecutionTimeoutError,
        SafeError("dataset_timeout", "Dataset execution timed out.", 504),
    ),
    (
        DatasetNotExecutableError,
        SafeError("dataset_not_executable", "The selected dataset cannot be executed.", 400),
    ),
    (
        DatasetExecutionProviderError,
        SafeError(
            "dataset_provider_unavailable", "The MySQL dataset provider is unavailable.", 503
        ),
    ),
    (
        QueryExecutionTimeoutError,
        SafeError("dataset_timeout", "The read-only query timed out.", 504),
    ),
    (
        QueryExecutionError,
        SafeError(
            "dataset_provider_unavailable", "The read-only query could not be completed.", 503
        ),
    ),
    (
        QueryFieldDiscoveryError,
        SafeError(
            "dataset_discovery_failed",
            "Dataset fields could not be discovered safely.",
            400,
        ),
    ),
    (
        RuntimePreviewCancelledError,
        SafeError("preview_cancelled", "Report preview was cancelled.", 409),
    ),
    (RuntimePreviewTimeoutError, SafeError("preview_timeout", "Report preview timed out.", 504)),
    (
        RuntimeReportLimitError,
        SafeError(
            "preview_output_limit", "Report preview exceeded a configured output limit.", 400
        ),
    ),
    (
        RuntimeBindingResolutionError,
        SafeError("binding_missing_field", "A report binding could not be resolved.", 400),
    ),
    (
        RuntimeUnsupportedBindingError,
        SafeError("binding_conflict", "A report binding is not supported for live preview.", 400),
    ),
    (
        RuntimeDatasetSelectionError,
        SafeError("preview_not_ready", "Select one primary dataset for live preview.", 400),
    ),
    (
        RuntimeBandConfigurationError,
        SafeError(
            "preview_not_ready", "The report Detail band is not ready for live preview.", 400
        ),
    ),
    (
        RuntimeReportRenderError,
        SafeError("preview_failed", "Report preview could not be completed.", 400),
    ),
    (
        RuntimeParameterDatasetError,
        SafeError("dataset_not_found", "The requested dataset was not found.", 404),
    ),
    (
        RuntimeParameterError,
        SafeError("parameter_invalid", "A runtime parameter value is invalid.", 400),
    ),
    (
        ReportSerializationError,
        SafeError("template_invalid", "The report template could not be loaded safely.", 400),
    ),
    (
        TemplateNotFoundError,
        SafeError("template_not_found", "The report template was not found.", 404),
    ),
    (
        TemplateIdError,
        SafeError("template_invalid", "The report template identifier is invalid.", 400),
    ),
    (
        TemplateValidationError,
        SafeError("template_invalid", "The report template is invalid.", 400),
    ),
    (TemplatePermissionError, SafeError("forbidden", "Permission denied.", 403)),
    (
        TemplateStorageError,
        SafeError("template_storage_error", "The report template could not be stored.", 500),
    ),
    (AssetNotFoundError, SafeError("asset_not_found", "The requested asset was not found.", 404)),
    (AssetIdError, SafeError("invalid_asset_id", "The asset identifier is invalid.", 400)),
    (AssetPermissionError, SafeError("asset_forbidden", "Asset permission denied.", 403)),
    (AssetTypeError, SafeError("unsupported_asset_type", "The asset type is not supported.", 400)),
    (AssetStorageError, SafeError("asset_storage_error", "The asset could not be stored.", 400)),
    (AssetError, SafeError("asset_error", "The asset operation failed.", 500)),
    (PermissionError, SafeError("forbidden", "Permission denied.", 403)),
    (
        FileNotFoundError,
        SafeError("template_not_found", "The requested resource was not found.", 404),
    ),
    (ValueError, SafeError("invalid_request", "The request could not be processed.", 400)),
    (SlimReportError, SafeError("invalid_request", "The request could not be processed.", 400)),
)


def map_safe_error(exc: BaseException) -> SafeError:
    """Map an exception deterministically without copying its text or type name."""
    if isinstance(exc, ReportSerializationError) and "newer version" in str(exc).casefold():
        return SafeError(
            "template_future_version",
            "This report template was created by a newer version of SLIM REPORT DESIGNER.",
            400,
        )
    for error_type, mapped in _MAPPINGS:
        if isinstance(exc, error_type):
            return mapped
    return SafeError("server_error", "The operation could not be completed.", 500)
