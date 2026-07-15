"""Flask adapter package for Slim Report Designer."""

__version__ = "0.7.0"

from .blueprint import create_blueprint
from .credentials import InMemoryRuntimeCredentialStore, RuntimeCredentialStore
from .errors import SafeError, map_safe_error
from .extension import SlimReportDesigner
from .preview import PreviewCancellationRegistry
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
    "InMemoryRuntimeCredentialStore",
    "PreviewCancellationRegistry",
    "PyMySQLTemplateProvider",
    "RuntimeCredentialStore",
    "SQLAlchemyTemplateProvider",
    "SafeError",
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
    "map_safe_error",
]
