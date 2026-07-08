"""Safe formula evaluation for computed report fields."""

from __future__ import annotations

import ast
import math
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

Resolver = Callable[[str], Any]

_IF_CALL_PATTERN = re.compile(r"\bif\s*\(")


@dataclass(frozen=True)
class FormulaEvaluation:
    """Result of a formula evaluation."""

    value: Any = ""
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error


class FormulaError(ValueError):
    """Raised for unsupported formula syntax or runtime failures."""


def evaluate_formula(
    formula: str,
    data: Mapping[str, Any] | None = None,
    *,
    resolver: Resolver | None = None,
) -> Any:
    """Evaluate a safe formula and return its value, or an empty string on failure."""
    return evaluate_formula_result(formula, data, resolver=resolver).value


def evaluate_formula_result(
    formula: str,
    data: Mapping[str, Any] | None = None,
    *,
    resolver: Resolver | None = None,
) -> FormulaEvaluation:
    """Evaluate a safe formula with a strict Python AST whitelist."""
    expression = str(formula or "").strip()
    if not expression:
        return FormulaEvaluation("")
    try:
        tree = ast.parse(_rewrite_reserved_functions(expression), mode="eval")
        value = _Evaluator(data or {}, resolver).visit(tree)
    except Exception as exc:
        return FormulaEvaluation("", str(exc))
    return FormulaEvaluation(value)


def evaluate_condition(
    condition: str,
    data: Mapping[str, Any] | None = None,
    *,
    resolver: Resolver | None = None,
) -> bool:
    """Evaluate a safe condition expression and return False on failure."""
    result = evaluate_formula_result(condition, data, resolver=resolver)
    return result.ok and _truthy(result.value)


def resolve_formula_identifier(identifier: str, data: Mapping[str, Any] | None = None) -> Any:
    """Resolve a dotted identifier from mapping data for standalone evaluator use."""
    value: Any = data or {}
    for part in str(identifier or "").split("."):
        if not part:
            return ""
        if isinstance(value, Mapping):
            value = value.get(part, "")
        else:
            value = getattr(value, part, "")
        if value is None:
            return ""
    return value


def _rewrite_reserved_functions(expression: str) -> str:
    return _IF_CALL_PATTERN.sub("if_(", expression)


class _Evaluator(ast.NodeVisitor):
    def __init__(self, data: Mapping[str, Any], resolver: Resolver | None) -> None:
        self.data = data
        self.resolver = resolver or (
            lambda identifier: resolve_formula_identifier(identifier, data)
        )

    def visit_Expression(self, node: ast.Expression) -> Any:
        return self.visit(node.body)

    def visit_Constant(self, node: ast.Constant) -> Any:
        if isinstance(node.value, str | int | float | bool) or node.value is None:
            return node.value
        raise FormulaError("Unsupported literal.")

    def visit_Name(self, node: ast.Name) -> Any:
        if node.id == "true":
            return True
        if node.id == "false":
            return False
        if node.id == "null":
            return None
        return self.resolver(node.id)

    def visit_Attribute(self, node: ast.Attribute) -> Any:
        return self.resolver(_attribute_path(node))

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Any:
        value = self.visit(node.operand)
        if isinstance(node.op, ast.USub):
            number = _to_number(value)
            if number is None:
                raise FormulaError("Unary minus requires a number.")
            return -number
        if isinstance(node.op, ast.UAdd):
            number = _to_number(value)
            if number is None:
                raise FormulaError("Unary plus requires a number.")
            return number
        if isinstance(node.op, ast.Not):
            return not _truthy(value)
        raise FormulaError("Unsupported unary operator.")

    def visit_BoolOp(self, node: ast.BoolOp) -> Any:
        if isinstance(node.op, ast.And):
            result: Any = True
            for value_node in node.values:
                result = self.visit(value_node)
                if not _truthy(result):
                    return result
            return result
        if isinstance(node.op, ast.Or):
            result = False
            for value_node in node.values:
                result = self.visit(value_node)
                if _truthy(result):
                    return result
            return result
        raise FormulaError("Unsupported boolean operator.")

    def visit_BinOp(self, node: ast.BinOp) -> Any:
        left = self.visit(node.left)
        right = self.visit(node.right)
        if isinstance(node.op, ast.Add):
            return _add(left, right)
        if isinstance(node.op, ast.Sub):
            return _numeric_binary(left, right, lambda a, b: a - b)
        if isinstance(node.op, ast.Mult):
            return _numeric_binary(left, right, lambda a, b: a * b)
        if isinstance(node.op, ast.Div):
            divisor = _to_number(right)
            if divisor in (None, 0):
                raise FormulaError("Division by zero or non-number.")
            left_number = _to_number(left)
            if left_number is None:
                raise FormulaError("Division requires numbers.")
            return left_number / divisor
        if isinstance(node.op, ast.Mod):
            divisor = _to_number(right)
            if divisor in (None, 0):
                raise FormulaError("Modulo by zero or non-number.")
            left_number = _to_number(left)
            if left_number is None:
                raise FormulaError("Modulo requires numbers.")
            return left_number % divisor
        raise FormulaError("Unsupported operator.")

    def visit_Compare(self, node: ast.Compare) -> bool:
        left = self.visit(node.left)
        for operator, comparator in zip(node.ops, node.comparators, strict=True):
            right = self.visit(comparator)
            if not _compare(left, right, operator):
                return False
            left = right
        return True

    def visit_Call(self, node: ast.Call) -> Any:
        if node.keywords:
            raise FormulaError("Keyword arguments are not supported.")
        if not isinstance(node.func, ast.Name):
            raise FormulaError("Unsupported function call.")
        function = _FUNCTIONS.get(node.func.id)
        if function is None:
            raise FormulaError(f"Unsupported function: {node.func.id}.")
        args = [self.visit(arg) for arg in node.args]
        return function(*args)

    def generic_visit(self, node: ast.AST) -> Any:
        raise FormulaError(f"Unsupported expression: {type(node).__name__}.")


def _attribute_path(node: ast.AST) -> str:
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        raise FormulaError("Unsupported identifier.")
    parts.append(current.id)
    return ".".join(reversed(parts))


def _add(left: Any, right: Any) -> Any:
    left_number = _to_number(left)
    right_number = _to_number(right)
    if left_number is not None and right_number is not None:
        return _format_numeric(left_number + right_number)
    return _text(left) + _text(right)


def _numeric_binary(left: Any, right: Any, operation: Callable[[float, float], float]) -> Any:
    left_number = _to_number(left)
    right_number = _to_number(right)
    if left_number is None or right_number is None:
        raise FormulaError("Operator requires numbers.")
    return _format_numeric(operation(left_number, right_number))


def _compare(left: Any, right: Any, operator: ast.cmpop) -> bool:
    if isinstance(operator, ast.Eq):
        return left == right
    if isinstance(operator, ast.NotEq):
        return left != right
    left_number = _to_number(left)
    right_number = _to_number(right)
    if left_number is not None and right_number is not None:
        a: Any = left_number
        b: Any = right_number
    else:
        a = _text(left)
        b = _text(right)
    if isinstance(operator, ast.Gt):
        return a > b
    if isinstance(operator, ast.GtE):
        return a >= b
    if isinstance(operator, ast.Lt):
        return a < b
    if isinstance(operator, ast.LtE):
        return a <= b
    raise FormulaError("Unsupported comparison.")


def _safe_concat(*values: Any) -> str:
    return "".join(_text(value) for value in values)


def _safe_number(value: Any, decimals: Any = 0) -> str:
    number = _to_number(value)
    places = _to_number(decimals)
    if number is None or places is None:
        return ""
    precision = max(0, min(int(places), 10))
    return f"{number:.{precision}f}"


def _safe_default(value: Any, fallback: Any = "") -> Any:
    return fallback if value in ("", None) else value


def _safe_if(condition: Any, true_value: Any = "", false_value: Any = "") -> Any:
    return true_value if _truthy(condition) else false_value


def _safe_contains(value: Any, text: Any) -> bool:
    return _text(text) in _text(value)


def _safe_starts_with(value: Any, text: Any) -> bool:
    return _text(value).startswith(_text(text))


def _safe_ends_with(value: Any, text: Any) -> bool:
    return _text(value).endswith(_text(text))


_FUNCTIONS: dict[str, Callable[..., Any]] = {
    "concat": _safe_concat,
    "upper": lambda value="": _text(value).upper(),
    "lower": lambda value="": _text(value).lower(),
    "title": lambda value="": _text(value).title(),
    "trim": lambda value="": _text(value).strip(),
    "number": _safe_number,
    "default": _safe_default,
    "if_": _safe_if,
    "contains": _safe_contains,
    "starts_with": _safe_starts_with,
    "ends_with": _safe_ends_with,
}


def _to_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _format_numeric(value: float) -> int | float:
    return int(value) if float(value).is_integer() else value


def _truthy(value: Any) -> bool:
    if value in ("", None, False):
        return False
    if isinstance(value, str) and value.strip().lower() in {"false", "0", "no"}:
        return False
    return bool(value)


def _text(value: Any) -> str:
    return "" if value is None else str(value)
