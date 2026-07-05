"""Minimal Flask demo for Slim Report Designer."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from flask import Flask, redirect

REPO_ROOT = Path(__file__).resolve().parents[2]
for package_src in (
    REPO_ROOT / "packages" / "slim_report_core" / "src",
    REPO_ROOT / "packages" / "slim_report_flask" / "src",
):
    if str(package_src) not in sys.path:
        sys.path.insert(0, str(package_src))

from slim_report_flask import SlimReportDesigner  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent

app = Flask(__name__)
app.config["SLIM_REPORT_TEMPLATE_DIR"] = str(BASE_DIR / "sample_templates")

designer = SlimReportDesigner()
designer.init_app(app)


@designer.provider("lab_result")
def lab_result(record_id: str) -> dict[str, dict[str, str]]:
    return {
        "patient": {
            "name": "JUAN DELA CRUZ",
            "age": "35",
            "sex": "MALE",
        },
        "order": {
            "id": record_id,
            "date": "2026-07-05",
        },
        "result": {
            "HGB": "14.5",
            "WBC": "7.2",
            "PLT": "250",
        },
    }


@app.get("/")
def index():
    return redirect("/report-designer/templates/lab_result/preview/ORDER-1001")


def ensure_sample_template() -> None:
    template_path = BASE_DIR / "sample_templates" / "lab_result.json"
    template_path.parent.mkdir(parents=True, exist_ok=True)
    json.loads(template_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    ensure_sample_template()
    app.run(debug=True)
