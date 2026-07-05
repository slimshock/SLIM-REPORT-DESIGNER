"""Widget registry for report object renderers."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..exceptions import WidgetValidationError
from .base import BaseWidget


@dataclass
class WidgetRegistry:
    """Registry for widget renderers keyed by object type."""

    _widgets: dict[str, BaseWidget] = field(default_factory=dict)

    def register(self, widget: BaseWidget) -> BaseWidget:
        """Register a widget instance."""
        widget_type = getattr(widget, "type", "").strip()
        if not widget_type:
            raise WidgetValidationError("Widget type must be a non-empty string.")

        self._widgets[widget_type] = widget
        return widget

    def get(self, widget_type: str) -> BaseWidget | None:
        """Return a widget by type, or None when it is not registered."""
        return self._widgets.get(widget_type)

    def list(self) -> list[str]:
        """Return registered widget types in stable order."""
        return sorted(self._widgets)


def create_default_widget_registry() -> WidgetRegistry:
    """Create a widget registry with built-in widgets."""
    from .field import FieldWidget
    from .line import LineWidget
    from .rectangle import RectangleWidget
    from .text import TextWidget

    registry = WidgetRegistry()
    registry.register(TextWidget())
    registry.register(FieldWidget())
    registry.register(LineWidget())
    registry.register(RectangleWidget())
    return registry

