"""SQL dialect contracts and built-in dialect implementations."""

from __future__ import annotations

import re
from collections.abc import Set
from typing import ClassVar, Protocol


class SQLDialect(Protocol):
    """Describe the SQL constructs accepted by a database dialect."""

    name: str

    def allowed_root_statements(self) -> Set[str]:
        """Return statement roots that may produce report data."""
        ...

    def forbidden_keywords(self) -> Set[str]:
        """Return statement keywords that may never appear as operations."""
        ...

    def forbidden_functions(self) -> Set[str]:
        """Return function names that may not be called."""
        ...

    def forbidden_clauses(self) -> Set[str]:
        """Return unsafe clause token sequences."""
        ...

    def validate_identifier(self, identifier: str) -> bool:
        """Return whether an identifier is valid for this dialect."""
        ...


class MySQLDialect:
    """Read-only SQL rules for the MySQL dialect."""

    name = "mysql"

    _ALLOWED_ROOT_STATEMENTS: ClassVar[frozenset[str]] = frozenset({"SELECT", "WITH"})
    _FORBIDDEN_KEYWORDS: ClassVar[frozenset[str]] = frozenset(
        {
            "INSERT",
            "UPDATE",
            "DELETE",
            "DROP",
            "ALTER",
            "TRUNCATE",
            "CREATE",
            "REPLACE",
            "MERGE",
            "CALL",
            "EXECUTE",
            "LOAD",
            "GRANT",
            "REVOKE",
            "SET",
            "USE",
            "SHOW",
            "DESCRIBE",
            "EXPLAIN",
        }
    )
    _FORBIDDEN_FUNCTIONS: ClassVar[frozenset[str]] = frozenset(
        {
            "SLEEP",
            "BENCHMARK",
            "LOAD_FILE",
            "GET_LOCK",
            "RELEASE_LOCK",
            "IS_FREE_LOCK",
            "IS_USED_LOCK",
            "MASTER_POS_WAIT",
            "SOURCE_POS_WAIT",
        }
    )
    _FORBIDDEN_CLAUSES: ClassVar[frozenset[str]] = frozenset(
        {
            "FOR UPDATE",
            "LOCK IN SHARE MODE",
            "INTO OUTFILE",
            "INTO DUMPFILE",
            "INTO @",
        }
    )
    _FORBIDDEN_COMMENT_MARKERS: ClassVar[frozenset[str]] = frozenset({"/*!"})
    _IDENTIFIER_RE: ClassVar[re.Pattern[str]] = re.compile(
        r"^(?:[A-Za-z_][A-Za-z0-9_]*|`(?:``|[^`])+`)"
        r"(?:\.(?:[A-Za-z_][A-Za-z0-9_]*|`(?:``|[^`])+`))*$"
    )

    def allowed_root_statements(self) -> frozenset[str]:
        return self._ALLOWED_ROOT_STATEMENTS

    def forbidden_keywords(self) -> frozenset[str]:
        return self._FORBIDDEN_KEYWORDS

    def forbidden_functions(self) -> frozenset[str]:
        return self._FORBIDDEN_FUNCTIONS

    def forbidden_clauses(self) -> frozenset[str]:
        return self._FORBIDDEN_CLAUSES

    def forbidden_comment_markers(self) -> frozenset[str]:
        """Return MySQL comment forms whose contents the server may execute."""
        return self._FORBIDDEN_COMMENT_MARKERS

    def validate_identifier(self, identifier: str) -> bool:
        return self._IDENTIFIER_RE.fullmatch(str(identifier)) is not None
