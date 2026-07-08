"""Asset provider APIs for report image assets."""

from __future__ import annotations

from .base import SAFE_ASSET_ID_PATTERN, AssetProvider, validate_asset_id
from .errors import (
    AssetError,
    AssetIdError,
    AssetNotFoundError,
    AssetPermissionError,
    AssetStorageError,
    AssetTypeError,
)
from .filesystem import FileSystemAssetProvider
from .resolver import ImageSourceResolver, ResolvedImageSource, resolve_image_source

__all__ = [
    "SAFE_ASSET_ID_PATTERN",
    "AssetError",
    "AssetIdError",
    "AssetNotFoundError",
    "AssetPermissionError",
    "AssetProvider",
    "AssetStorageError",
    "AssetTypeError",
    "FileSystemAssetProvider",
    "ImageSourceResolver",
    "ResolvedImageSource",
    "resolve_image_source",
    "validate_asset_id",
]
