"""Flask adapter package for Slim Report Designer."""

__version__ = "0.5.0a1"

from .blueprint import create_blueprint
from .extension import SlimReportDesigner

__all__ = ["SlimReportDesigner", "create_blueprint"]
