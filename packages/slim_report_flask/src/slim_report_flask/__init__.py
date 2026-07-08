"""Flask adapter package for Slim Report Designer."""

__version__ = "0.6.0a0"

from .blueprint import create_blueprint
from .extension import SlimReportDesigner
from .storage import (
    DBAPITemplateProvider,
    FileSystemTemplateProvider,
    PyMySQLTemplateProvider,
    SQLAlchemyTemplateProvider,
    TemplateExistsError,
    TemplateIdError,
    TemplateNotFoundError,
    TemplatePermissionError,
    TemplateProvider,
    TemplateRecord,
    TemplateStorageError,
    TemplateStore,
    TemplateValidationError,
)

__all__ = [
    "DBAPITemplateProvider",
    "FileSystemTemplateProvider",
    "PyMySQLTemplateProvider",
    "SQLAlchemyTemplateProvider",
    "SlimReportDesigner",
    "TemplateExistsError",
    "TemplateIdError",
    "TemplateNotFoundError",
    "TemplatePermissionError",
    "TemplateProvider",
    "TemplateRecord",
    "TemplateStorageError",
    "TemplateStore",
    "TemplateValidationError",
    "create_blueprint",
]
