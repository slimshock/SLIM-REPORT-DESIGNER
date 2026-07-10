"""Core exceptions for Slim Report Designer."""


class SlimReportError(Exception):
    """Base exception for Slim Report Designer core errors."""


class ReportValidationError(SlimReportError):
    """Raised when report data does not match the expected structure."""


class ReportSerializationError(SlimReportError):
    """Raised when report JSON cannot be read or written."""


class ReportObjectNotFoundError(SlimReportError):
    """Raised when a report object cannot be found by id."""


class WidgetValidationError(ReportValidationError):
    """Raised when a report object is invalid for its widget type."""


class ExporterError(SlimReportError):
    """Raised when a report cannot be exported."""


class DataSourceError(SlimReportError):
    """Base exception for report data-source metadata errors."""


class DataSourceValidationError(DataSourceError, ReportValidationError):
    """Raised when a report data source is invalid."""


class DatasetValidationError(DataSourceError, ReportValidationError):
    """Raised when a report dataset is invalid."""


class CredentialResolutionError(DataSourceError):
    """Raised when a credential reference cannot be resolved safely."""
