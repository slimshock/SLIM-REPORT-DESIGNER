"""Public building blocks for SQL validation."""

from .dialects import MySQLDialect, SQLDialect
from .exceptions import (
    EmptySQLError,
    InvalidSQLParameterError,
    InvalidSQLSyntaxError,
    MultipleStatementsError,
    SQLValidationError,
    UnsafeSQLConstructError,
    UnsupportedStatementError,
)
from .parser import SQLParser
from .validator import SQLValidationPolicy, SQLValidationResult, SQLValidator

__all__ = [
    "EmptySQLError",
    "InvalidSQLParameterError",
    "InvalidSQLSyntaxError",
    "MultipleStatementsError",
    "MySQLDialect",
    "SQLDialect",
    "SQLParser",
    "SQLValidationError",
    "SQLValidationPolicy",
    "SQLValidationResult",
    "SQLValidator",
    "UnsafeSQLConstructError",
    "UnsupportedStatementError",
]
