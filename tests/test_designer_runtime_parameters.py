from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "packages/slim_report_designer_ui/slim_report_designer_ui/static"


def test_runtime_parameter_dialog_and_dataset_entry_point_are_present() -> None:
    html = (UI_ROOT / "index.html").read_text(encoding="utf-8")
    datasets = (UI_ROOT / "js/datasets.js").read_text(encoding="utf-8")
    designer = (UI_ROOT / "js/designer.js").read_text(encoding="utf-8")

    assert 'id="runtime-parameter-modal"' in html
    assert 'aria-labelledby="runtime-parameter-title"' in html
    assert "Report Parameters" in html
    assert "Validate Parameters" in html
    assert 'button("Parameters"' in datasets
    assert 'dataset.sourceType === "query"' in datasets
    assert "createRuntimeParameterDialog" in designer


def test_runtime_dialog_is_temporary_and_uses_authoritative_api() -> None:
    source = (UI_ROOT / "js/runtime_parameters.js").read_text(encoding="utf-8")
    api = (UI_ROOT / "js/api.js").read_text(encoding="utf-8")

    assert "collectRuntimeParameters" in source
    assert "getRuntimeParameterSchema" in source
    assert "validateRuntimeParameters" in source
    assert "localStorage" not in source
    assert "sessionStorage" not in source
    assert "history" not in source.lower()
    assert "console." not in source
    assert "execute" not in source.lower()
    assert "URLSearchParams" not in source
    assert "runtime-parameters/validate" in api


def test_runtime_parameter_javascript_modules_parse() -> None:
    for relative_path in (
        "packages/slim_report_designer_ui/slim_report_designer_ui/static/js/runtime_parameters.js",
        "packages/slim_report_designer_ui/slim_report_designer_ui/static/js/datasets.js",
        "packages/slim_report_designer_ui/slim_report_designer_ui/static/js/designer.js",
    ):
        result = subprocess.run(
            ["node", "--check", relative_path],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
