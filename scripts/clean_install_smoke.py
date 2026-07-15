"""Install built wheels in an isolated venv and verify public imports/assets."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import venv
from pathlib import Path
from shutil import copytree

ROOT = Path(__file__).resolve().parents[1]


def create_environment(root: Path, name: str) -> Path:
    environment = root / name
    venv.EnvBuilder(with_pip=True).create(environment)
    return environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def install(python: Path, dist_dir: Path, *requirements: str) -> None:
    subprocess.run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--find-links",
            str(dist_dir),
            *requirements,
        ],
        check=True,
        cwd=python.parent,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dist_dir", nargs="?", default="dist")
    args = parser.parse_args()
    dist_dir = Path(args.dist_dir).resolve()
    wheels = sorted(dist_dir.glob("*.whl"))
    if not wheels:
        print("No wheels found.")
        return 1
    with tempfile.TemporaryDirectory(prefix="slim-report-wheel-") as temp:
        temp_root = Path(temp)
        core_python = create_environment(temp_root, "core")
        install(core_python, dist_dir, "slim-report-core==0.7.0")
        subprocess.run(
            [
                str(core_python),
                "-c",
                (
                    "import importlib.util, slim_report_core; "
                    "assert slim_report_core.__version__ == '0.7.0'; "
                    "assert importlib.util.find_spec('flask') is None; "
                    "assert importlib.util.find_spec('pymysql') is None"
                ),
            ],
            check=True,
            cwd=temp_root,
        )

        mysql_python = create_environment(temp_root, "mysql")
        install(mysql_python, dist_dir, "slim-report-core[mysql]==0.7.0")
        subprocess.run(
            [
                str(mysql_python),
                "-c",
                (
                    "import importlib.util, pymysql, slim_report_core; "
                    "assert pymysql.__version__; "
                    "assert importlib.util.find_spec('flask') is None"
                ),
            ],
            check=True,
            cwd=temp_root,
        )

        full_python = create_environment(temp_root, "full")
        install(
            full_python,
            dist_dir,
            *map(str, wheels),
            "slim-report-flask[database]==0.7.0",
            "python-dotenv>=1,<2",
        )
        subprocess.run(
            [
                str(full_python),
                "-c",
                (
                    "import slim_report_core, slim_report_flask, slim_report_designer_ui; "
                    "from slim_report_designer_ui import static_file; "
                    "assert static_file('index.html').is_file(); "
                    "assert slim_report_core.__version__ == '0.7.0'"
                ),
            ],
            check=True,
            cwd=temp_root,
        )

        demo = temp_root / "flask_database_app"
        ignored_demo_names = {".env", ".venv-demo", "__pycache__", "report_templates.db"}
        copytree(
            ROOT / "examples" / "flask_database_app",
            demo,
            ignore=lambda _path, names: {name for name in names if name in ignored_demo_names},
        )
        demo_command = (
            "import runpy; "
            f"namespace = runpy.run_path({str(demo / 'app.py')!r}, run_name='wheel_demo'); "
            "app = namespace['app']; app.config['TESTING'] = True; "
            "response = app.test_client().get('/report-designer/designer'); "
            "assert response.status_code == 200; "
            "assert b'Report Designer' in response.data"
        )
        subprocess.run(
            [str(full_python), "-c", demo_command],
            check=True,
            cwd=temp_root,
        )
    print("Core-only, MySQL-extra, full-stack, and wheel-demo smoke tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
