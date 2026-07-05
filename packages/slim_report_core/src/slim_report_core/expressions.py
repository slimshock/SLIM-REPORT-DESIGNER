"""Safe expression resolution for report text and fields."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date, datetime
from typing import Any, Final

_EXPRESSION_PATTERN: Final = re.compile(r"\{\{\s*(.*?)\s*\}\}")
_MISSING: Final = object()


def resolve_expression(expression: str, data: Any, context: Any = None) -> Any:
    """Resolve a single expression against data and optional render context.

    Supported expressions are intentionally limited to dotted paths and safe
    zero-argument functions such as ``today()`` and ``now()``.
    """
    normalized = _strip_expression_markers(expression)
    if not normalized:
        return ""

    function_value = _resolve_safe_function(normalized)
    if function_value is not _MISSING:
        return function_value

    data_value = _resolve_path(normalized, data)
    if data_value is not _MISSING:
        return _empty_if_none(data_value)

    context_value = _resolve_path(normalized, context)
    if context_value is not _MISSING:
        return _empty_if_none(context_value)

    return ""


def resolve_text(text: str, data: Any, context: Any = None) -> str:
    """Resolve all ``{{ expression }}`` placeholders in text."""

    def replace(match: re.Match[str]) -> str:
        value = resolve_expression(match.group(1), data, context=context)
        if value is None:
            return ""
        return str(value)

    return _EXPRESSION_PATTERN.sub(replace, text)


def _strip_expression_markers(expression: str) -> str:
    value = expression.strip()
    match = _EXPRESSION_PATTERN.fullmatch(value)
    if match:
        return match.group(1).strip()
    return value


def _resolve_safe_function(expression: str) -> Any:
    if not expression.endswith("()"):
        return _MISSING

    function_name = expression[:-2].strip()
    if function_name == "today":
        return date.today().isoformat()
    if function_name == "now":
        return datetime.now().isoformat(timespec="seconds")
    return _MISSING


def _resolve_path(path: str, source: Any) -> Any:
    if source is None:
        return _MISSING

    current = source
    for part in path.split("."):
        if not _is_safe_path_part(part):
            return _MISSING

        current = _resolve_path_part(current, part)
        if current is _MISSING:
            return _MISSING

    return current


def _resolve_path_part(value: Any, part: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(part, _MISSING)

    if part.startswith("_"):
        return _MISSING

    if not hasattr(value, part):
        return _MISSING

    resolved = getattr(value, part)
    if callable(resolved):
        return _MISSING

    return resolved


def _is_safe_path_part(part: str) -> bool:
    return bool(part) and not part.startswith("_") and part.replace("_", "").isalnum()


def _empty_if_none(value: Any) -> Any:
    if value is None:
        return ""
    return value

