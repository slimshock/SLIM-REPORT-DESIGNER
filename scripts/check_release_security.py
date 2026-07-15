"""Run deterministic checks against files eligible for a release."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_SUFFIXES = {".db", ".sqlite", ".sqlite3", ".pyc"}
FORBIDDEN_NAMES = {".env"}
SECRET_KEYS = {"password", "resolvedPassword", "runtimePassword", "credentialValue"}
REQUIRED_RELEASE_FILES = {
    "CHANGELOG.md",
    "docs/release-notes-0.7.0.md",
    "docs/migration-0.7.0.md",
}


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [ROOT / line for line in result.stdout.splitlines() if line]


def find_secret_keys(value: Any, path: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in SECRET_KEYS:
                findings.append(child_path)
            findings.extend(find_secret_keys(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(find_secret_keys(child, f"{path}[{index}]"))
    return findings


def main() -> int:
    failures: list[str] = []
    files = tracked_files()
    for path in files:
        relative = path.relative_to(ROOT).as_posix()
        if path.name in FORBIDDEN_NAMES or path.suffix.casefold() in FORBIDDEN_SUFFIXES:
            failures.append(f"forbidden tracked artifact: {relative}")
        if path.suffix.casefold() == ".json" and (
            "template" in relative.casefold() or "/reports/" in relative.casefold()
        ):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                failures.append(f"cannot inspect JSON {relative}: {exc}")
                continue
            failures.extend(
                f"plaintext secret key in {relative}: {finding}"
                for finding in find_secret_keys(payload)
            )
        if relative.startswith(("packages/", "examples/")) and path.is_file():
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for known_secret in ("release-secret", "secret-value", "super-secret-password"):
                if known_secret in text:
                    failures.append(f"known test secret in release input: {relative}")
    for relative in REQUIRED_RELEASE_FILES:
        if not (ROOT / relative).is_file():
            failures.append(f"required release document missing: {relative}")
    if "0.7.0" not in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"):
        failures.append("CHANGELOG.md does not mention release 0.7.0")
    if failures:
        print("Release security check failed:")
        print("\n".join(f"- {item}" for item in failures))
        return 1
    print(f"Release security check passed for {len(files)} tracked files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
