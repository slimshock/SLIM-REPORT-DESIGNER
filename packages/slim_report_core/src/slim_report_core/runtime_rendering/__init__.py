"""Framework-independent live report rendering contracts."""

from .binding import RuntimeBindingResolver, RuntimeValueFormatter
from .errors import (
    RuntimeBandConfigurationError,
    RuntimeBindingResolutionError,
    RuntimeDatasetSelectionError,
    RuntimePreviewCancelledError,
    RuntimePreviewTimeoutError,
    RuntimeReportLimitError,
    RuntimeReportRenderError,
    RuntimeUnsupportedBindingError,
)
from .models import (
    RuntimePreviewOptions,
    RuntimePreviewPolicy,
    RuntimePreviewResult,
    RuntimePreviewSummary,
    RuntimePreviewWarning,
    RuntimeRenderContext,
)
from .service import RuntimeReportRenderService

__all__ = [
    "RuntimeBandConfigurationError",
    "RuntimeBindingResolutionError",
    "RuntimeBindingResolver",
    "RuntimeDatasetSelectionError",
    "RuntimePreviewCancelledError",
    "RuntimePreviewOptions",
    "RuntimePreviewPolicy",
    "RuntimePreviewResult",
    "RuntimePreviewSummary",
    "RuntimePreviewTimeoutError",
    "RuntimePreviewWarning",
    "RuntimeRenderContext",
    "RuntimeReportLimitError",
    "RuntimeReportRenderError",
    "RuntimeReportRenderService",
    "RuntimeUnsupportedBindingError",
    "RuntimeValueFormatter",
]
