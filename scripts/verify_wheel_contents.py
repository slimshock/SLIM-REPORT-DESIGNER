"""Verify required resources and forbidden artifacts in built wheels."""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

FORBIDDEN_NAMES = {".env"}
FORBIDDEN_SUFFIXES = {".db", ".sqlite", ".sqlite3", ".pyc"}
UI_ASSETS = {
    "slim_report_designer_ui/static/index.html",
    "slim_report_designer_ui/static/css/designer.css",
    "slim_report_designer_ui/static/js/designer.js",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dist_dir", nargs="?", default="dist")
    args = parser.parse_args()
    wheels = sorted(Path(args.dist_dir).glob("*.whl"))
    failures: list[str] = []
    if not wheels:
        failures.append("no wheels found")
    for wheel in wheels:
        with zipfile.ZipFile(wheel) as archive:
            names = set(archive.namelist())
        for name in names:
            path = Path(name)
            if path.name in FORBIDDEN_NAMES or path.suffix.casefold() in FORBIDDEN_SUFFIXES:
                failures.append(f"{wheel.name}: forbidden artifact {name}")
        if wheel.name.startswith("slim_report_designer_ui-"):
            failures.extend(
                f"{wheel.name}: missing {asset}" for asset in UI_ASSETS if asset not in names
            )
    if failures:
        print("Wheel content verification failed:")
        print("\n".join(f"- {item}" for item in failures))
        return 1
    print(f"Wheel content verification passed for {len(wheels)} wheels.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
