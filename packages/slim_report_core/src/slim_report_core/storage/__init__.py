"""Framework-agnostic template storage providers."""

from __future__ import annotations

from importlib import import_module

from .base import (
    SAFE_TEMPLATE_ID_PATTERN,
    TemplateProvider,
    TemplateRecord,
    record_from_summary,
    template_metadata,
    validate_template_id,
)
from .errors import (
    TemplateExistsError,
    TemplateIdError,
    TemplateNotFoundError,
    TemplatePermissionError,
    TemplateStorageError,
    TemplateValidationError,
)
from .filesystem import FileSystemTemplateProvider, TemplateStore

SQLAlchemyTemplateProvider = import_module(
    ".sqlalchemy",
    __name__,
).SQLAlchemyTemplateProvider

__all__ = [
    "SAFE_TEMPLATE_ID_PATTERN",
    "FileSystemTemplateProvider",
    "SQLAlchemyTemplateProvider",
    "TemplateExistsError",
    "TemplateIdError",
    "TemplateNotFoundError",
    "TemplatePermissionError",
    "TemplateProvider",
    "TemplateRecord",
    "TemplateStorageError",
    "TemplateStore",
    "TemplateValidationError",
    "record_from_summary",
    "template_metadata",
    "validate_template_id",
]
