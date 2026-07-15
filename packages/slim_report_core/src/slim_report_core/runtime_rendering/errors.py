"""Safe failures raised while rendering live report previews."""

from ..exceptions import ReportValidationError


class RuntimeReportRenderError(ReportValidationError):
    """Base error for live report rendering."""


class RuntimeDatasetSelectionError(RuntimeReportRenderError):
    """Raised when one primary runtime dataset cannot be selected."""


class RuntimeBindingResolutionError(RuntimeReportRenderError):
    """Raised when a structured dataset binding cannot be resolved."""


class RuntimeUnsupportedBindingError(RuntimeReportRenderError):
    """Raised when an object type cannot consume a dataset binding."""


class RuntimeBandConfigurationError(RuntimeReportRenderError):
    """Raised when Detail-band runtime semantics are ambiguous or invalid."""


class RuntimeReportLimitError(RuntimeReportRenderError):
    """Raised before a bounded preview limit would be exceeded."""


class RuntimePreviewCancelledError(RuntimeReportRenderError):
    """Raised when cancellation is observed during preview."""


class RuntimePreviewTimeoutError(RuntimeReportRenderError):
    """Raised when the preview deadline is exceeded."""
