from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "packages/slim_report_designer_ui/slim_report_designer_ui/static"


def test_live_preview_uses_existing_preview_command_and_sandboxed_iframe() -> None:
    html = (UI_ROOT / "index.html").read_text(encoding="utf-8")
    designer = (UI_ROOT / "js/designer.js").read_text(encoding="utf-8")

    assert 'id="live-preview-modal"' in html
    assert 'id="live-preview-frame"' in html
    assert 'sandbox="allow-same-origin"' in html
    assert "allow-scripts" not in html
    assert 'command === "preview"' in designer
    assert "primaryRuntimeDataset" in designer
    assert "collectRuntimeParameters" in designer
    assert 'actionLabel: "Preview Report"' in designer


def test_live_preview_request_and_runtime_state_are_not_persisted() -> None:
    source = (UI_ROOT / "js/live_preview.js").read_text(encoding="utf-8")
    api = (UI_ROOT / "js/api.js").read_text(encoding="utf-8")

    assert "startLivePreview" in source
    assert "cancelLivePreview" in source
    assert "srcdoc" in source
    assert 'ui.frame.srcdoc = ""' in source
    assert "localStorage" not in source
    assert "sessionStorage" not in source
    assert "history" not in source.lower()
    assert "console." not in source
    assert "/designer/preview/live" in api
    assert "parameterValues" in api
    assert "URLSearchParams" not in source


def test_live_preview_javascript_modules_parse() -> None:
    for relative_path in (
        "packages/slim_report_designer_ui/slim_report_designer_ui/static/js/api.js",
        "packages/slim_report_designer_ui/slim_report_designer_ui/static/js/designer.js",
        "packages/slim_report_designer_ui/slim_report_designer_ui/static/js/live_preview.js",
        "packages/slim_report_designer_ui/slim_report_designer_ui/static/js/runtime_parameters.js",
    ):
        result = subprocess.run(
            ["node", "--check", relative_path],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
