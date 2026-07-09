"""Asset provider exceptions."""

from __future__ import annotations


class AssetError(Exception):
    """Base exception for report asset failures."""


class AssetNotFoundError(AssetError, FileNotFoundError):
    """Raised when an asset cannot be found."""


class AssetIdError(AssetError, ValueError):
    """Raised when an asset id is unsafe or invalid."""


class AssetPermissionError(AssetError, PermissionError):
    """Raised when an asset operation is not allowed."""


class AssetStorageError(AssetError):
    """Raised when asset storage fails."""


class AssetTypeError(AssetError, ValueError):
    """Raised when an asset type or extension is not allowed."""
