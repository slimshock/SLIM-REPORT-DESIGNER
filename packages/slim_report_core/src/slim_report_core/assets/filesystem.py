"""Filesystem-backed report asset provider."""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any, BinaryIO

from .base import validate_asset_id
from .errors import (
    AssetNotFoundError,
    AssetPermissionError,
    AssetStorageError,
    AssetTypeError,
)

DEFAULT_ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
ALLOWED_IMAGE_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
}


class FileSystemAssetProvider:
    """Filesystem-backed provider for reusable report image assets."""

    def __init__(
        self,
        asset_folder: str | Path,
        *,
        base_url: str | None = None,
        allow_save: bool = False,
        allow_delete: bool = False,
        allowed_extensions: set[str] | None = None,
        max_size_bytes: int | None = None,
    ) -> None:
        self.root = Path(asset_folder)
        self.base_url = base_url.rstrip("/") if base_url else None
        self.allow_save = allow_save
        self.allow_delete = allow_delete
        self.allowed_extensions = {
            _normalize_extension(item)
            for item in (allowed_extensions or DEFAULT_ALLOWED_EXTENSIONS)
        }
        self.max_size_bytes = max_size_bytes

    def ensure(self) -> None:
        """Create the asset directory if needed."""
        self.root.mkdir(parents=True, exist_ok=True)

    def list_assets(self) -> list[dict[str, Any]]:
        """List image assets in the configured folder."""
        self.ensure()
        assets = []
        for path in sorted(self.root.iterdir()):
            if not path.is_file() or not self._extension_allowed(path.suffix):
                continue
            assets.append(self._metadata_for_path(path))
        return assets

    def get_asset(self, asset_id: str) -> dict[str, Any]:
        """Return metadata for one asset."""
        return self._metadata_for_path(self.path_for(asset_id))

    def open_asset(self, asset_id: str) -> BinaryIO:
        """Open an asset for binary reading."""
        path = self.path_for(asset_id)
        return path.open("rb")

    def get_asset_url(self, asset_id: str) -> str | None:
        """Return a configured public URL for an asset."""
        if self.base_url is None:
            return None
        path = self.path_for(asset_id)
        return f"{self.base_url}/{path.stem}"

    def exists(self, asset_id: str) -> bool:
        """Return whether an asset exists."""
        try:
            self.path_for(asset_id)
        except (AssetNotFoundError, AssetStorageError, ValueError):
            return False
        return True

    def save_asset(
        self,
        asset_id: str,
        content: bytes,
        content_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Save an asset when saving is explicitly enabled."""
        if not self.allow_save:
            raise AssetPermissionError("Asset saving is disabled.")
        safe_id = validate_asset_id(asset_id)
        if not isinstance(content, bytes):
            raise AssetStorageError("Asset content must be bytes.")
        if self.max_size_bytes is not None and len(content) > self.max_size_bytes:
            raise AssetStorageError("Asset exceeds maximum allowed size.")
        extension = self._extension_for_save(safe_id, content_type, metadata or {})
        path = self._safe_path(f"{self._id_without_extension(safe_id)}{extension}")
        self.ensure()
        path.write_bytes(content)
        return self._metadata_for_path(path)

    def delete_asset(self, asset_id: str) -> bool:
        """Delete an asset when deletion is explicitly enabled."""
        if not self.allow_delete:
            raise AssetPermissionError("Asset deletion is disabled.")
        path = self.path_for(asset_id)
        path.unlink()
        return True

    def path_for(self, asset_id: str) -> Path:
        """Resolve an asset id to a safe image path inside the asset folder."""
        safe_id = validate_asset_id(asset_id)
        explicit_extension = self._explicit_image_extension(safe_id)
        if explicit_extension:
            path = self._safe_path(safe_id)
            if not path.exists():
                raise AssetNotFoundError(f"Asset not found: {asset_id}")
            return path

        self.ensure()
        matches = [
            path
            for path in sorted(self.root.iterdir())
            if path.is_file()
            and path.stem == safe_id
            and self._extension_allowed(path.suffix)
        ]
        if not matches:
            raise AssetNotFoundError(f"Asset not found: {asset_id}")
        return self._safe_path(matches[0].name)

    def _metadata_for_path(self, path: Path) -> dict[str, Any]:
        if not path.exists() or not path.is_file():
            raise AssetNotFoundError(f"Asset not found: {path.stem}")
        if not self._extension_allowed(path.suffix):
            raise AssetTypeError(f"Unsupported asset extension: {path.suffix}")
        stat = path.stat()
        content_type = (
            mimetypes.guess_type(path.name)[0] or _content_type_for_extension(path.suffix)
        )
        return {
            "id": path.stem,
            "name": _name_from_id(path.stem),
            "filename": path.name,
            "content_type": content_type,
            "size": stat.st_size,
            "url": f"{self.base_url}/{path.stem}" if self.base_url else None,
            "category": "",
            "created_at": None,
            "updated_at": None,
        }

    def _extension_for_save(
        self,
        asset_id: str,
        content_type: str | None,
        metadata: dict[str, Any],
    ) -> str:
        explicit = self._explicit_image_extension(asset_id)
        if explicit:
            return explicit
        filename = metadata.get("filename")
        if isinstance(filename, str):
            extension = _normalize_extension(Path(filename).suffix)
            if self._extension_allowed(extension):
                return extension
        if content_type:
            extension = ALLOWED_IMAGE_TYPES.get(str(content_type).split(";", 1)[0].strip().lower())
            if extension and self._extension_allowed(extension):
                return extension
        raise AssetTypeError("Asset extension or supported image content type is required.")

    def _explicit_image_extension(self, asset_id: str) -> str:
        extension = _normalize_extension(Path(asset_id).suffix)
        return extension if self._extension_allowed(extension) else ""

    def _id_without_extension(self, asset_id: str) -> str:
        extension = self._explicit_image_extension(asset_id)
        return asset_id[: -len(extension)] if extension else asset_id

    def _extension_allowed(self, extension: str) -> bool:
        return _normalize_extension(extension) in self.allowed_extensions

    def _safe_path(self, filename: str) -> Path:
        candidate = (self.root / filename).resolve()
        root = self.root.resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise AssetStorageError("Asset path escapes the asset folder.") from exc
        if not self._extension_allowed(candidate.suffix):
            raise AssetTypeError(f"Unsupported asset extension: {candidate.suffix}")
        return candidate


def _normalize_extension(value: str) -> str:
    text = str(value or "").strip().lower()
    if text and not text.startswith("."):
        text = f".{text}"
    return text


def _content_type_for_extension(extension: str) -> str | None:
    extension = _normalize_extension(extension)
    if extension == ".svg":
        return "image/svg+xml"
    for content_type, mapped_extension in ALLOWED_IMAGE_TYPES.items():
        if mapped_extension == extension or (extension == ".jpeg" and content_type == "image/jpeg"):
            return content_type
    return None


def _name_from_id(asset_id: str) -> str:
    return str(asset_id).replace("_", " ").replace("-", " ").title()
