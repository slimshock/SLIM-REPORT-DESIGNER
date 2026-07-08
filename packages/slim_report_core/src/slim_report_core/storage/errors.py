"""Storage exceptions for report template providers."""

from __future__ import annotations


class TemplateStorageError(Exception):
    """Base exception for template storage failures."""


class TemplateNotFoundError(TemplateStorageError, FileNotFoundError):
    """Raised when a template cannot be found."""


class TemplateExistsError(TemplateStorageError):
    """Raised when a template already exists."""


class TemplateValidationError(TemplateStorageError, ValueError):
    """Raised when a template or storage value is invalid."""


class TemplatePermissionError(TemplateStorageError, PermissionError):
    """Raised when a provider denies a storage operation."""


class TemplateIdError(TemplateValidationError):
    """Raised when a template id is unsafe or invalid."""
