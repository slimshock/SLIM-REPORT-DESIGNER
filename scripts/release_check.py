"""Run local release quality gates without publishing artifacts."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = sorted((ROOT / "packages").glob("slim_report_*"))
DIST = ROOT / "dist"


def run(*command: str) -> None:
    print(f"+ {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live-mysql", action="store_true")
    parser.add_argument("--browser", action="store_true")
    args = parser.parse_args()
    run(sys.executable, "scripts/check_versions.py")
    run(sys.executable, "scripts/check_release_security.py")
    run(sys.executable, "-m", "ruff", "check", ".")
    run(sys.executable, "-m", "mypy", "packages", "tests")
    marker_parts = []
    if not args.live_mysql:
        marker_parts.append("not mysql_integration")
    if not args.browser:
        marker_parts.append("not browser")
    pytest_command = [sys.executable, "-m", "pytest", "-q"]
    if marker_parts:
        pytest_command.extend(["-m", " and ".join(marker_parts)])
    run(*pytest_command)
    if DIST.exists():
        if DIST.resolve().parent != ROOT.resolve():
            raise RuntimeError("Refusing to remove a dist directory outside the repository root.")
        shutil.rmtree(DIST)
    DIST.mkdir()
    for package in PACKAGES:
        run(sys.executable, "-m", "build", "--outdir", str(DIST), str(package))
    artifacts = [str(path) for path in sorted(DIST.iterdir()) if path.is_file()]
    run(sys.executable, "-m", "twine", "check", *artifacts)
    run(sys.executable, "scripts/verify_wheel_contents.py", str(DIST))
    run(sys.executable, "scripts/clean_install_smoke.py", str(DIST))
    print("Release quality gates passed. No artifacts were published.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
