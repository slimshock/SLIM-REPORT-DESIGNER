"""Image source resolution helpers."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any

from .errors import AssetError


@dataclass(frozen=True)
class ResolvedImageSource:
    """Resolved image source for HTML or PDF rendering."""

    source: str = ""
    content: bytes | None = None
    content_type: str | None = None

    @property
    def is_empty(self) -> bool:
        return not self.source and not self.content

    def as_data_url(self) -> str:
        """Return a data URL when binary content is available."""
        if self.source.startswith("data:image/"):
            return self.source
        if self.content is None:
            return self.source
        content_type = self.content_type or "application/octet-stream"
        encoded = base64.b64encode(self.content).decode("ascii")
        return f"data:{content_type};base64,{encoded}"


class ImageSourceResolver:
    """Resolve image sources from direct values or asset references."""

    def __init__(self, asset_provider: Any | None = None) -> None:
        self.asset_provider = asset_provider

    def resolve(
        self,
        *,
        source: Any = None,
        asset_id: Any = None,
        prefer_url: bool = True,
        prefer_bytes: bool = False,
    ) -> ResolvedImageSource:
        """Resolve an image source without raising for missing assets."""
        clean_asset_id = _clean_image_value(asset_id)
        if clean_asset_id:
            resolved = self._resolve_asset(clean_asset_id, prefer_url=prefer_url)
            if not resolved.is_empty:
                return resolved
        clean_source = _clean_image_value(source)
        if not clean_source:
            return ResolvedImageSource()
        if prefer_bytes and clean_source.startswith("data:image/"):
            return ResolvedImageSource(source=clean_source)
        return ResolvedImageSource(source=clean_source)

    def _resolve_asset(self, asset_id: str, *, prefer_url: bool) -> ResolvedImageSource:
        provider = self.asset_provider
        if provider is None:
            return ResolvedImageSource()
        if prefer_url:
            try:
                url = provider.get_asset_url(asset_id)
            except AssetError:
                return ResolvedImageSource()
            if url:
                return ResolvedImageSource(source=str(url))
        try:
            metadata = provider.get_asset(asset_id)
            with provider.open_asset(asset_id) as asset_file:
                content = asset_file.read()
        except (AssetError, OSError):
            return ResolvedImageSource()
        return ResolvedImageSource(
            content=content,
            content_type=str(metadata.get("content_type") or "") or None,
        )


def resolve_image_source(
    *,
    source: Any = None,
    asset_id: Any = None,
    asset_provider: Any | None = None,
    prefer_url: bool = True,
    prefer_bytes: bool = False,
) -> ResolvedImageSource:
    """Resolve a report image source using an optional asset provider."""
    return ImageSourceResolver(asset_provider).resolve(
        source=source,
        asset_id=asset_id,
        prefer_url=prefer_url,
        prefer_bytes=prefer_bytes,
    )


def _clean_image_value(value: Any) -> str:
    text = str(value or "").strip()
    if text.lower() in {"", "none", "null", "undefined"}:
        return ""
    if text.startswith("{{") and text.endswith("}}"):
        return ""
    return text
