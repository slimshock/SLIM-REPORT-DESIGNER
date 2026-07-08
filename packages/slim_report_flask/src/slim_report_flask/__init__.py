"""Flask adapter package for Slim Report Designer."""

__version__ = "0.6.0a0"

from .blueprint import create_blueprint
from .extension import SlimReportDesigner
from .storage import FileSystemTemplateProvider, TemplateProvider

__all__ = [
    "FileSystemTemplateProvider",
    "SlimReportDesigner",
    "TemplateProvider",
    "create_blueprint",
]
