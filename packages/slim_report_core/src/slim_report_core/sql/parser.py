"""Dialect-aware parsing isolated behind the project's SQL parser abstraction."""

from __future__ import annotations

import re
from collections.abc import Iterable, Set
from dataclasses import dataclass

import sqlglot
from sqlglot import Dialect, exp
from sqlglot.errors import ParseError, TokenError
from sqlglot.tokens import Token, TokenType

from .dialects import SQLDialect

_PARAMETER_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class ParsedSQL:
    """A library-neutral summary of parsed SQL used by ``SQLValidator``."""

    root_statement: str
    statement_count: int
    separator_count: int
    statement_types: tuple[str, ...]
    function_names: tuple[str, ...]
    parameters: tuple[str, ...]
    invalid_parameter_styles: tuple[str, ...]
    forbidden_clauses: tuple[str, ...]
    forbidden_comments: tuple[str, ...]
    has_cte: bool
    has_union: bool
    is_query: bool
    parse_error: str | None = None


class SQLParser:
    """Wrap sqlglot and expose only the facts needed by validation policies."""

    def parse(self, sql: str, dialect: SQLDialect) -> ParsedSQL:
        """Parse SQL using the selected dialect without executing it."""
        try:
            tokenizer = Dialect.get_or_raise(dialect.name).tokenizer_class()
            tokens = tokenizer.tokenize(sql)
        except (TokenError, ValueError) as exc:
            return self._failed_parse(str(exc))

        root_statement = self._root_statement(tokens)
        separator_count = sum(token.token_type is TokenType.SEMICOLON for token in tokens)
        parameters, invalid_styles = self._parameters(sql, tokens)
        forbidden_clauses = self._matched_clauses(tokens, dialect.forbidden_clauses())
        forbidden_comments = self._matched_comment_markers(sql, tokens, dialect)

        try:
            statements = [
                statement
                for statement in sqlglot.parse(sql, read=dialect.name)
                if statement is not None
            ]
        except (ParseError, TokenError, ValueError) as exc:
            return ParsedSQL(
                root_statement=root_statement,
                statement_count=0,
                separator_count=separator_count,
                statement_types=(),
                function_names=(),
                parameters=parameters,
                invalid_parameter_styles=invalid_styles,
                forbidden_clauses=forbidden_clauses,
                forbidden_comments=forbidden_comments,
                has_cte=False,
                has_union=False,
                is_query=False,
                parse_error=str(exc),
            )

        nodes = [node for statement in statements for node in statement.walk()]
        statement_types = _ordered_unique(node.key.upper() for node in nodes)
        function_names = _ordered_unique(
            self._function_name(node) for node in nodes if isinstance(node, exp.Func)
        )
        return ParsedSQL(
            root_statement=root_statement,
            statement_count=len(statements),
            separator_count=separator_count,
            statement_types=statement_types,
            function_names=function_names,
            parameters=parameters,
            invalid_parameter_styles=invalid_styles,
            forbidden_clauses=forbidden_clauses,
            forbidden_comments=forbidden_comments,
            has_cte=any(isinstance(node, exp.With) for node in nodes),
            has_union=any(isinstance(node, exp.Union) for node in nodes),
            is_query=bool(statements)
            and all(isinstance(statement, exp.Query) for statement in statements),
        )

    @staticmethod
    def _failed_parse(message: str) -> ParsedSQL:
        return ParsedSQL(
            root_statement="",
            statement_count=0,
            separator_count=0,
            statement_types=(),
            function_names=(),
            parameters=(),
            invalid_parameter_styles=(),
            forbidden_clauses=(),
            forbidden_comments=(),
            has_cte=False,
            has_union=False,
            is_query=False,
            parse_error=message,
        )

    @staticmethod
    def _root_statement(tokens: list[Token]) -> str:
        for token in tokens:
            if token.token_type is not TokenType.SEMICOLON:
                return token.text.upper()
        return ""

    @staticmethod
    def _function_name(node: exp.Func) -> str:
        if isinstance(node, exp.Anonymous):
            return node.name.upper()
        return node.sql_name().upper()

    @staticmethod
    def _matched_clauses(tokens: list[Token], clauses: Set[str]) -> tuple[str, ...]:
        comparable = [
            "<QUOTED>"
            if token.token_type is TokenType.IDENTIFIER
            or "STRING" in token.token_type.name
            else token.text.upper()
            for token in tokens
        ]
        matches: list[str] = []
        for clause in sorted(str(item).upper() for item in clauses):
            parts = clause.split()
            width = len(parts)
            if any(comparable[index : index + width] == parts for index in range(len(tokens))):
                matches.append(clause)
        return tuple(matches)

    @staticmethod
    def _parameters(sql: str, tokens: list[Token]) -> tuple[tuple[str, ...], tuple[str, ...]]:
        parameters: list[str] = []
        invalid_styles: list[str] = []
        for index, token in enumerate(tokens):
            if token.token_type is TokenType.COLON:
                following = tokens[index + 1] if index + 1 < len(tokens) else None
                if (
                    following is not None
                    and following.token_type is TokenType.VAR
                    and token.end + 1 == following.start
                    and _PARAMETER_NAME_RE.fullmatch(following.text) is not None
                ):
                    if following.text not in parameters:
                        parameters.append(following.text)
                else:
                    invalid_styles.append(":name")
                continue

            if token.token_type is TokenType.PLACEHOLDER:
                invalid_styles.append("?")
                continue

            fragment = sql[token.start :]
            if token.token_type is TokenType.MOD:
                if re.match(r"%\([A-Za-z_][A-Za-z0-9_]*\)s", fragment):
                    invalid_styles.append("%(name)s")
                elif re.match(r"%s\b", fragment):
                    invalid_styles.append("%s")
            elif token.text == "$" and re.match(
                r"\$\{[A-Za-z_][A-Za-z0-9_]*\}", fragment
            ):
                invalid_styles.append("${name}")
            elif token.token_type is TokenType.L_BRACE and re.match(
                r"\{\{[A-Za-z_][A-Za-z0-9_]*\}\}", fragment
            ):
                invalid_styles.append("{{name}}")

        return tuple(parameters), _ordered_unique(invalid_styles)

    @staticmethod
    def _matched_comment_markers(
        sql: str,
        tokens: list[Token],
        dialect: SQLDialect,
    ) -> tuple[str, ...]:
        marker_provider = getattr(dialect, "forbidden_comment_markers", None)
        if marker_provider is None:
            return ()

        searchable = list(sql.upper())
        for token in tokens:
            if token.token_type is TokenType.IDENTIFIER or "STRING" in token.token_type.name:
                searchable[token.start : token.end + 1] = " " * (token.end - token.start + 1)
        searchable_sql = "".join(searchable)
        return tuple(
            marker
            for marker in sorted(str(item).upper() for item in marker_provider())
            if marker in searchable_sql
        )


def _ordered_unique(values: Iterable[object]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values))
