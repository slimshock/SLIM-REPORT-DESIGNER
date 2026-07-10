"""Thread-safe registry for framework-independent data-source providers."""

from __future__ import annotations

from threading import RLock

from .base import DataSourceProvider
from .errors import (
    DuplicateDataSourceProviderError,
    UnsupportedDataSourceProviderError,
)


class DataSourceProviderRegistry:
    """Register providers by deterministic, case-insensitive type names."""

    def __init__(self) -> None:
        self._providers: dict[str, DataSourceProvider] = {}
        self._lock = RLock()

    def register(self, provider: DataSourceProvider, *, replace: bool = False) -> None:
        """Register a provider, optionally replacing the existing type."""
        provider_type = self._normalize_type(getattr(provider, "provider_type", ""))
        with self._lock:
            if provider_type in self._providers and not replace:
                raise DuplicateDataSourceProviderError(
                    f"A data-source provider is already registered for {provider_type!r}."
                )
            self._providers[provider_type] = provider

    def unregister(self, provider_type: str) -> None:
        """Remove a registered provider type."""
        normalized = self._normalize_type(provider_type)
        with self._lock:
            if normalized not in self._providers:
                raise UnsupportedDataSourceProviderError(
                    f"No data-source provider is registered for {normalized!r}."
                )
            del self._providers[normalized]

    def get(self, provider_type: str) -> DataSourceProvider:
        """Return the provider registered for a type."""
        normalized = self._normalize_type(provider_type)
        with self._lock:
            try:
                return self._providers[normalized]
            except KeyError as exc:
                raise UnsupportedDataSourceProviderError(
                    f"No data-source provider is registered for {normalized!r}."
                ) from exc

    def has(self, provider_type: str) -> bool:
        """Return whether a provider type is registered."""
        normalized = self._normalize_type(provider_type)
        with self._lock:
            return normalized in self._providers

    def available(self) -> tuple[str, ...]:
        """Return registered provider names in deterministic order."""
        with self._lock:
            return tuple(sorted(self._providers))

    @staticmethod
    def _normalize_type(provider_type: object) -> str:
        normalized = str(provider_type).strip().lower()
        if not normalized:
            raise UnsupportedDataSourceProviderError(
                "A data-source provider type must not be empty."
            )
        return normalized
