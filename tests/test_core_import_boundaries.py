"""Import boundary tests for the framework-agnostic core package."""

from __future__ import annotations

import ast
from pathlib import Path

FORBIDDEN_IMPORT_ROOTS = {
    "django",
    "fastapi",
    "flask",
    "sqlalchemy",
    "starlette",
}

FORBIDDEN_FLASK_ADAPTER_IMPORT_ROOTS = {
    "django",
    "fastapi",
    "sqlalchemy",
    "starlette",
}


def test_core_package_does_not_import_frameworks() -> None:
    violations = find_forbidden_imports(Path("packages/slim_report_core/src/slim_report_core"))

    assert violations == []


def test_cli_package_does_not_import_frameworks() -> None:
    violations = find_forbidden_imports(Path("packages/slim_report_cli/src/slim_report_cli"))

    assert violations == []


def test_flask_adapter_does_not_import_other_frameworks() -> None:
    violations = find_forbidden_imports(
        Path("packages/slim_report_flask/src/slim_report_flask"),
        forbidden_roots=FORBIDDEN_FLASK_ADAPTER_IMPORT_ROOTS,
    )

    assert violations == []


def find_forbidden_imports(
    package_src: Path,
    *,
    forbidden_roots: set[str] = FORBIDDEN_IMPORT_ROOTS,
) -> list[str]:
    violations: list[str] = []

    for path in package_src.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".", maxsplit=1)[0]
                    if root in forbidden_roots:
                        violations.append(f"{path}: imports {alias.name}")

            if isinstance(node, ast.ImportFrom) and node.module:
                root = node.module.split(".", maxsplit=1)[0]
                if root in forbidden_roots:
                    violations.append(f"{path}: imports from {node.module}")

    return violations
