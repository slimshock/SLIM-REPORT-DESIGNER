"""Built-in widget system for Slim Report Designer."""

from .base import BaseWidget
from .field import FieldWidget
from .image import ImageWidget
from .line import LineWidget
from .rectangle import RectangleWidget
from .registry import WidgetRegistry, create_default_widget_registry
from .text import TextWidget

__all__ = [
    "BaseWidget",
    "FieldWidget",
    "ImageWidget",
    "LineWidget",
    "RectangleWidget",
    "TextWidget",
    "WidgetRegistry",
    "create_default_widget_registry",
]
