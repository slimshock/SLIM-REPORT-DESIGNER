"""Verify synchronized distribution and import package versions."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_VERSION = "0.7.0"
PACKAGES = {
    "slim_report_core": "src/slim_report_core/__init__.py",
    "slim_report_flask": "src/slim_report_flask/__init__.py",
    "slim_report_designer_ui": "slim_report_designer_ui/__init__.py",
    "slim_report_cli": "src/slim_report_cli/__init__.py",
    "slim_report_django": "src/slim_report_django/__init__.py",
    "slim_report_fastapi": "src/slim_report_fastapi/__init__.py",
}


def module_version(path: Path) -> str | None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets
        ):
            return ast.literal_eval(node.value)
    return None


def main() -> int:
    failures: list[str] = []
    for package, module_path in PACKAGES.items():
        package_root = ROOT / "packages" / package
        metadata = tomllib.loads((package_root / "pyproject.toml").read_text(encoding="utf-8"))
        project_version = metadata["project"]["version"]
        import_version = module_version(package_root / module_path)
        if project_version != EXPECTED_VERSION or import_version != EXPECTED_VERSION:
            failures.append(
                f"{package}: metadata={project_version!r}, import={import_version!r}"
            )
    if failures:
        print("Version synchronization failed:")
        print("\n".join(f"- {item}" for item in failures))
        return 1
    print(f"Version synchronization passed: {EXPECTED_VERSION} across {len(PACKAGES)} packages.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
