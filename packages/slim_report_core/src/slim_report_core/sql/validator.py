"""Framework-independent SQL validation policies and orchestration."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from .dialects import SQLDialect
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

if TYPE_CHECKING:
    from ..data_sources import ReportDataset


@dataclass(frozen=True)
class SQLValidationPolicy:
    """Limits and optional query features enforced by ``SQLValidator``."""

    max_query_length: int = 100_000
    max_parameters: int = 100
    allow_cte: bool = True
    allow_union: bool = True

    def __post_init__(self) -> None:
        if self.max_query_length < 1:
            raise ValueError("max_query_length must be at least 1.")
        if self.max_parameters < 0:
            raise ValueError("max_parameters must not be negative.")


@dataclass(frozen=True)
class SQLValidationResult:
    """The safe, normalized metadata produced for a validated query."""

    normalized_sql: str
    root_statement: str
    parameters: tuple[str, ...]
    dialect: str
    warnings: tuple[str, ...] = ()


class SQLValidator:
    """Validate report SQL without opening a database connection or executing SQL."""

    def __init__(
        self,
        dialect: SQLDialect,
        policy: SQLValidationPolicy | None = None,
        parser: SQLParser | None = None,
    ) -> None:
        self.dialect = dialect
        self.policy = policy or SQLValidationPolicy()
        self._parser = parser or SQLParser()

    def validate(self, sql: str) -> SQLValidationResult:
        """Validate one read-only query and return its normalized metadata."""
        if not isinstance(sql, str) or not sql.strip():
            raise EmptySQLError("SQL query must not be empty.")
        if len(sql) > self.policy.max_query_length:
            raise SQLValidationError(
                "SQL query exceeds the maximum length of "
                f"{self.policy.max_query_length} characters."
            )

        stripped_sql = sql.strip()
        parsed = self._parser.parse(stripped_sql, self.dialect)

        if parsed.separator_count > 1 or (
            parsed.separator_count == 1 and not stripped_sql.endswith(";")
        ):
            raise MultipleStatementsError("SQL must contain exactly one statement.")
        if parsed.statement_count > 1:
            raise MultipleStatementsError("SQL must contain exactly one statement.")
        if parsed.forbidden_comments:
            raise UnsafeSQLConstructError(
                "Executable SQL comments are not allowed by the selected dialect."
            )
        if parsed.invalid_parameter_styles:
            style = parsed.invalid_parameter_styles[0]
            raise InvalidSQLParameterError(
                f"Unsupported SQL parameter syntax {style!r}; use :name parameters only."
            )
        if self.dialect.name == "mysql" and parsed.has_user_variables:
            raise UnsafeSQLConstructError("MySQL user variables are not allowed in report queries.")
        if self.dialect.name == "mysql" and parsed.has_system_variables:
            raise UnsafeSQLConstructError(
                "MySQL system variables are not allowed in report queries."
            )
        if self.dialect.name == "mysql" and parsed.has_assignment_operator:
            raise UnsafeSQLConstructError(
                "SQL assignment operators are not allowed in report queries."
            )
        if parsed.forbidden_clauses:
            clause = parsed.forbidden_clauses[0]
            raise UnsafeSQLConstructError(f"SQL clause is not allowed: {clause}.")

        root_statement = parsed.root_statement
        if root_statement not in self.dialect.allowed_root_statements():
            display_root = root_statement or "unknown"
            raise UnsupportedStatementError(
                f"SQL statement {display_root!r} is not supported; "
                "only SELECT and WITH are allowed."
            )
        if parsed.parse_error is not None or parsed.statement_count != 1:
            raise InvalidSQLSyntaxError(
                f"SQL could not be parsed using the {self.dialect.name} dialect."
            )
        if not parsed.is_query:
            raise UnsupportedStatementError("SQL must be a SELECT query.")

        forbidden_statements = set(parsed.statement_types).intersection(
            self.dialect.forbidden_keywords()
        )
        if forbidden_statements:
            keyword = sorted(forbidden_statements)[0]
            raise UnsafeSQLConstructError(f"SQL operation is not allowed: {keyword}.")

        forbidden_functions = set(parsed.function_names).intersection(
            self.dialect.forbidden_functions()
        )
        if forbidden_functions:
            function = sorted(forbidden_functions)[0]
            raise UnsafeSQLConstructError(f"SQL function is not allowed: {function}().")

        if parsed.has_cte and not self.policy.allow_cte:
            raise UnsupportedStatementError("Common table expressions are disabled by policy.")
        if parsed.has_union and not self.policy.allow_union:
            raise UnsupportedStatementError("UNION queries are disabled by policy.")
        if len(parsed.parameters) > self.policy.max_parameters:
            raise InvalidSQLParameterError(
                f"SQL query exceeds the maximum of {self.policy.max_parameters} parameters."
            )

        normalized_sql = stripped_sql
        if normalized_sql.endswith(";"):
            normalized_sql = normalized_sql[:-1].rstrip()
        return SQLValidationResult(
            normalized_sql=normalized_sql,
            root_statement=root_statement,
            parameters=parsed.parameters,
            dialect=self.dialect.name,
        )

    def validate_dataset(self, dataset: ReportDataset) -> SQLValidationResult:
        """Validate a query dataset and reconcile its declared parameters."""
        query = getattr(dataset, "query", None)
        if not isinstance(query, str) or not query.strip():
            raise EmptySQLError("Dataset query must not be empty.")

        result = self.validate(query)
        declared_names = [self._parameter_name(parameter) for parameter in dataset.parameters]
        duplicate = self._first_duplicate(declared_names)
        if duplicate is not None:
            raise InvalidSQLParameterError(
                f"Dataset contains a duplicate parameter declaration: {duplicate}."
            )

        declared = set(declared_names)
        missing = [name for name in result.parameters if name not in declared]
        if missing:
            names = ", ".join(f":{name}" for name in missing)
            raise InvalidSQLParameterError(
                f"SQL references parameters that are not declared by the dataset: {names}."
            )

        referenced = set(result.parameters)
        warnings = tuple(
            f"Dataset parameter {name!r} is not referenced by the SQL query."
            for name in declared_names
            if name not in referenced
        )
        return replace(result, warnings=result.warnings + warnings)

    @staticmethod
    def _parameter_name(parameter: Any) -> str:
        name = getattr(parameter, "name", None)
        if not isinstance(name, str) or not name:
            raise InvalidSQLParameterError("Every dataset parameter must have a name.")
        return name

    @staticmethod
    def _first_duplicate(names: list[str]) -> str | None:
        seen: set[str] = set()
        for name in names:
            normalized = name.lower()
            if normalized in seen:
                return name
            seen.add(normalized)
        return None
