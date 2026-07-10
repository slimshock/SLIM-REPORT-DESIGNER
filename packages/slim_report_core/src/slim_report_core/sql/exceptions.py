"""Exceptions raised by the SQL validation engine."""

from ..exceptions import SlimReportError


class SQLValidationError(SlimReportError):
    """Base exception for SQL that cannot be accepted safely."""


class EmptySQLError(SQLValidationError):
    """Raised when no SQL query was provided."""


class MultipleStatementsError(SQLValidationError):
    """Raised when SQL contains more than one statement."""


class UnsupportedStatementError(SQLValidationError):
    """Raised when the root statement is not allowed by the policy or dialect."""


class UnsafeSQLConstructError(SQLValidationError):
    """Raised when SQL contains a construct that is unsafe for report queries."""


class InvalidSQLParameterError(SQLValidationError):
    """Raised when SQL uses an unsupported or inconsistent parameter declaration."""


class InvalidSQLSyntaxError(SQLValidationError):
    """Raised when SQL cannot be parsed in the selected dialect."""
