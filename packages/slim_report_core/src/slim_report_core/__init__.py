"""Framework-agnostic core package for Slim Report Designer."""

__version__ = "0.0.0"

from .constants import DEFAULT_REPORT_VERSION
from .data import DataContext, DataProviderRegistry
from .exceptions import (
    ExporterError,
    ReportObjectNotFoundError,
    ReportSerializationError,
    ReportValidationError,
    SlimReportError,
    WidgetValidationError,
)
from .exporters import (
    BaseExporter,
    ExporterRegistry,
    HTMLExporter,
    PDFExporter,
    create_default_exporter_registry,
)
from .expressions import resolve_expression, resolve_text
from .models import (
    ReportAsset,
    ReportBand,
    ReportMetadata,
    ReportObject,
    ReportPage,
    ReportTemplate,
)
from .report import Report, create_default_template
from .widgets import (
    BaseWidget,
    FieldWidget,
    LineWidget,
    RectangleWidget,
    TextWidget,
    WidgetRegistry,
    create_default_widget_registry,
)

__all__ = [
    "DEFAULT_REPORT_VERSION",
    "BaseExporter",
    "BaseWidget",
    "DataContext",
    "DataProviderRegistry",
    "ExporterError",
    "ExporterRegistry",
    "FieldWidget",
    "HTMLExporter",
    "LineWidget",
    "PDFExporter",
    "RectangleWidget",
    "Report",
    "ReportAsset",
    "ReportBand",
    "ReportMetadata",
    "ReportObject",
    "ReportObjectNotFoundError",
    "ReportPage",
    "ReportSerializationError",
    "ReportTemplate",
    "ReportValidationError",
    "SlimReportError",
    "TextWidget",
    "WidgetRegistry",
    "WidgetValidationError",
    "create_default_exporter_registry",
    "create_default_template",
    "create_default_widget_registry",
    "resolve_expression",
    "resolve_text",
]
