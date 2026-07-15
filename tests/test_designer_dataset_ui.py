from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "packages/slim_report_designer_ui/slim_report_designer_ui/static"


def test_dataset_manager_entry_point_and_accessible_modal_are_present() -> None:
    html = (UI_ROOT / "index.html").read_text(encoding="utf-8")
    toolbar = (UI_ROOT / "js/toolbar.js").read_text(encoding="utf-8")
    designer = (UI_ROOT / "js/designer.js").read_text(encoding="utf-8")

    assert '<span class="brand-mark">SR</span>' in html
    assert "<span>Report Designer</span>" in html
    assert 'id="dataset-modal"' in html
    assert 'aria-modal="true"' in html
    assert 'aria-labelledby="dataset-title"' in html
    assert '"datasets", "Datasets"' in toolbar
    assert 'command === "datasets"' in designer
    assert "Data Sources" in toolbar


def test_dataset_parameter_helpers_preserve_order_and_detect_stale_configurations() -> None:
    module_path = "./packages/slim_report_designer_ui/slim_report_designer_ui/static/js/datasets.js"
    script = """
import {
  parameterLabel,
  queryConfigurationFingerprint,
  reconcileDetectedParameters
} from '__MODULE_PATH__';

const existing = [{ name: 'CLIENT_ID', dataType: 'integer', required: false, label: 'Client' }];
const parameters = reconcileDetectedParameters(existing, ['date_from', 'client_id', 'date_to']);
if (parameters.map((item) => item.name).join(',') !== 'date_from,client_id,date_to') {
  throw new Error('detected order was not preserved');
}
if (parameters[1].dataType !== 'integer' || parameters[1].name !== 'client_id') {
  throw new Error('existing definitions were not reconciled case-insensitively');
}
if (parameterLabel('patient_id') !== 'Patient ID') {
  throw new Error('parameter label generation failed');
}
const before = queryConfigurationFingerprint('SELECT :id', parameters);
parameters[0].dataType = 'date';
const after = queryConfigurationFingerprint('SELECT :id', parameters);
if (before === after) {
  throw new Error('parameter type changes did not invalidate discovery');
}
""".replace("__MODULE_PATH__", module_path)

    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_dataset_ui_keeps_discovery_values_transient_and_uses_management_api() -> None:
    source = (UI_ROOT / "js/datasets.js").read_text(encoding="utf-8")
    api = (UI_ROOT / "js/api.js").read_text(encoding="utf-8")

    assert "localStorage" not in source
    assert "sessionStorage" not in source
    assert "temporaryValues = {}" in source
    assert "parameterValues: readTemporaryValues(form)" in source
    assert "sampleRows" not in source
    assert "pymysql" not in source.lower()
    assert "information_schema" not in source.lower()
    assert 'dataSourceRequest("/designer/query/validate", "POST"' in api
    assert 'dataSourceRequest("/designer/query/discover", "POST"' in api
    assert "URLSearchParams" not in source
