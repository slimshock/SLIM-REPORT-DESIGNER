"""Framework-agnostic asset provider interface."""

from __future__ import annotations

import re
from typing import BinaryIO, Protocol

from .errors import AssetIdError

SAFE_ASSET_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")


class AssetProvider(Protocol):
    """Small interface for resolving reusable report image assets."""

    def list_assets(self) -> list[dict]:
        """Return asset metadata dictionaries."""
        ...

    def get_asset(self, asset_id: str) -> dict:
        """Return one asset metadata dictionary."""
        ...

    def open_asset(self, asset_id: str) -> BinaryIO:
        """Open an asset for binary reading."""
        ...

    def get_asset_url(self, asset_id: str) -> str | None:
        """Return a public URL for an asset, when one is configured."""
        ...

    def exists(self, asset_id: str) -> bool:
        """Return whether an asset exists."""
        ...

    def save_asset(
        self,
        asset_id: str,
        content: bytes,
        content_type: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        """Persist and return asset metadata."""
        ...

    def delete_asset(self, asset_id: str) -> bool:
        """Delete an asset if supported."""
        ...


def validate_asset_id(asset_id: str) -> str:
    """Validate and return a safe asset id."""
    if not isinstance(asset_id, str):
        raise AssetIdError("Asset id must be a string.")
    cleaned = asset_id.strip()
    if not cleaned:
        raise AssetIdError("Asset id must not be empty.")
    if ":" in cleaned or "/" in cleaned or "\\" in cleaned or ".." in cleaned:
        raise AssetIdError(f"Invalid asset id: {asset_id}.")
    if not SAFE_ASSET_ID_PATTERN.fullmatch(cleaned):
        raise AssetIdError(f"Invalid asset id: {asset_id}.")
    return cleaned
