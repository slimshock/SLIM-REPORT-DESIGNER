"""Data context and provider registry for report rendering."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .exceptions import ReportValidationError
from .expressions import resolve_expression as resolve_core_expression
from .expressions import resolve_text as resolve_core_text

DataProvider = Callable[..., Any]


@dataclass
class DataProviderRegistry:
    """Registry for named data provider callables."""

    _providers: dict[str, DataProvider] = field(default_factory=dict)

    def register(self, name: str, func: DataProvider) -> DataProvider:
        """Register a callable data provider by name."""
        normalized_name = _validate_provider_name(name)
        if not callable(func):
            raise ReportValidationError(f"Data provider must be callable: {normalized_name}.")

        self._providers[normalized_name] = func
        return func

    def get(self, name: str) -> DataProvider | None:
        """Return a registered data provider, or None when it does not exist."""
        return self._providers.get(name)

    def list(self) -> list[str]:
        """Return registered provider names in stable order."""
        return sorted(self._providers)

    def resolve(self, name: str, *args: Any, **kwargs: Any) -> Any:
        """Call a registered provider by name."""
        provider = self.get(name)
        if provider is None:
            raise ReportValidationError(f"Data provider is not registered: {name}.")
        return provider(*args, **kwargs)


@dataclass
class DataContext:
    """Container for report data, render context, and data providers."""

    data: Any = field(default_factory=dict)
    context: Any = field(default_factory=dict)
    providers: DataProviderRegistry = field(default_factory=DataProviderRegistry)

    def resolve_expression(self, expression: str) -> Any:
        """Resolve one expression against this context."""
        return resolve_core_expression(expression, self.data, context=self.context)

    def resolve_text(self, text: str) -> str:
        """Resolve all expressions in text against this context."""
        return resolve_core_text(text, self.data, context=self.context)


def _validate_provider_name(name: str) -> str:
    normalized_name = name.strip()
    if not normalized_name:
        raise ReportValidationError("Data provider name must be a non-empty string.")
    return normalized_name

