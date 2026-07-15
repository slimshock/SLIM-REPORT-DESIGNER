"""Framework-agnostic static designer UI package."""

from __future__ import annotations

from importlib.resources import files
from importlib.resources.abc import Traversable

__all__ = ["get_designer_static_path", "static_file", "static_root"]

__version__ = "0.7.0"


def static_root() -> Traversable:
    """Return the package resource root for static designer files."""
    return files(__package__) / "static"


def get_designer_static_path() -> Traversable:
    """Return the designer static resource root."""
    return static_root()


def static_file(relative_path: str) -> Traversable:
    """Return a static designer resource by relative path."""
    normalized = relative_path.strip("/").replace("\\", "/") or "index.html"
    return static_root() / normalized
