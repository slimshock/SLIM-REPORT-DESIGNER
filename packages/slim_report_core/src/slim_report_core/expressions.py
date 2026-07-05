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
    name, indexes = _split_path_part(part)
    if name is _MISSING:
        return _MISSING
    if name:
        value = _resolve_named_path_part(value, name)
        if value is _MISSING:
            return _MISSING
    for index in indexes:
        if not isinstance(value, list):
            return _MISSING
        if index is None:
            value = value[0] if value else _MISSING
        elif 0 <= index < len(value):
            value = value[index]
        else:
            return _MISSING
        if value is _MISSING:
            return _MISSING
    return value


def _resolve_named_path_part(value: Any, part: str) -> Any:
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
    name, indexes = _split_path_part(part)
    return name is not _MISSING and (bool(name) or bool(indexes))


def _split_path_part(part: str) -> tuple[str, list[int | None]] | tuple[object, list[int | None]]:
    if not part:
        return _MISSING, []
    name = ""
    indexes: list[int | None] = []
    cursor = 0
    while cursor < len(part):
        char = part[cursor]
        if char == "[":
            close = part.find("]", cursor + 1)
            if close == -1:
                return _MISSING, []
            raw_index = part[cursor + 1:close]
            if raw_index == "":
                indexes.append(None)
            elif raw_index.isdigit():
                indexes.append(int(raw_index))
            else:
                return _MISSING, []
            cursor = close + 1
            continue
        if indexes:
            return _MISSING, []
        name += char
        cursor += 1
    if name and (name.startswith("_") or not name.replace("_", "").isalnum()):
        return _MISSING, []
    return name, indexes


def _empty_if_none(value: Any) -> Any:
    if value is None:
        return ""
    return value
