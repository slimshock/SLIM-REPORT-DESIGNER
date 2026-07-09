"""Backward-compatible storage exports for the Flask adapter."""

from __future__ import annotations

from slim_report_core.storage import (
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
    record_from_summary,
    validate_template_id,
)

_record_from_summary = record_from_summary

__all__ = [
    "DBAPITemplateProvider",
    "FileSystemTemplateProvider",
    "PyMySQLTemplateProvider",
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
    "_record_from_summary",
    "record_from_summary",
    "validate_template_id",
]
