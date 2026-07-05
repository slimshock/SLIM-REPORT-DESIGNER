"""Flask adapter package for Slim Report Designer."""

__version__ = "0.0.0"

from .blueprint import create_blueprint
from .extension import SlimReportDesigner

__all__ = ["SlimReportDesigner", "create_blueprint"]
