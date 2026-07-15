from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "packages/slim_report_designer_ui/slim_report_designer_ui/static"


def test_dataset_fields_panel_has_accessible_management_and_insert_controls() -> None:
    html = (UI_ROOT / "index.html").read_text(encoding="utf-8")
    designer = (UI_ROOT / "js/designer.js").read_text(encoding="utf-8")

    assert 'for="field-search"' in html
    assert ">Search Fields<" in html
    assert 'id="field-search-clear"' in html
    assert 'id="dataset-manager-open"' in html
    assert 'id="dataset-field-insert"' in html
    assert "application/x-slim-report-dataset-field" in designer
    assert "event.clientX - rect.left" in designer
    assert "event.clientY - rect.top" in designer
    assert "pymysql" not in designer.lower()
    assert "information_schema" not in designer.lower()


def test_dataset_binding_helpers_enforce_stored_fields_and_band_context() -> None:
    module_path = "./packages/slim_report_designer_ui/slim_report_designer_ui/static/js/objects.js"
    script = """
import {
  clearDatasetFieldBinding,
  datasetFieldBindingStatus,
  datasetFieldDragPayload,
  datasetFieldObjectDefaults,
  getBandDatasetId,
  normalizeTemplate,
  parseDatasetFieldDragPayload,
  setDatasetFieldBinding,
  setObjectBand
} from '__MODULE_PATH__';

const template = normalizeTemplate({
  page: { width: 600, height: 800 },
  datasets: [
    { id: 'patients', name: 'Patients', fields: [
      { name: 'full_name', dataType: 'string' },
      { name: 'result_value', dataType: 'decimal' },
      { name: 'scan', dataType: 'binary' }
    ] },
    { id: 'orders', name: 'Orders', fields: [{ name: 'id', dataType: 'integer' }] }
  ],
  bands: [
    { id: 'detail', type: 'detail', y: 0, height: 400 },
    { id: 'footer', type: 'page_footer', y: 400, height: 100 }
  ],
  objects: [{
    id: 'name', type: 'text', text: 'Name', band: 'detail', x: 12, y: 10,
    width: 200, height: 24, properties: { custom: true }
  }]
});
const object = template.objects[0];
if (!setDatasetFieldBinding(template, object, 'patients', 'full_name')) {
  throw new Error('valid binding was rejected');
}
if (object.text !== '{{patients.full_name}}' || object.properties.dataBinding) {
  throw new Error('binding was not canonical or placeholder was incorrect');
}
if (getBandDatasetId(template.bands[0]) !== 'patients') {
  throw new Error('band context was not established');
}
if (setDatasetFieldBinding(template, object, 'patients', 'FULL_NAME')) {
  throw new Error('field matching was not exact');
}
if (setObjectBand(template, object, 'footer') !== true) {
  throw new Error('bound object could not move to an empty band');
}
if (getBandDatasetId(template.bands[0]) || getBandDatasetId(template.bands[1]) !== 'patients') {
  throw new Error('band context was not transferred');
}
template.bands[0].dataBinding = { datasetId: 'orders' };
if (setObjectBand(template, object, 'detail') !== false || object.band !== 'footer') {
  throw new Error('cross-dataset band movement was not rejected atomically');
}
clearDatasetFieldBinding(template, object);
if (object.text !== '{{patients.full_name}}' || getBandDatasetId(template.bands[1])) {
  throw new Error('clear destroyed static text or retained empty band context');
}
object.dataBinding = { type: 'datasetField', datasetId: 'patients', field: 'missing' };
if (datasetFieldBindingStatus(template, object).state !== 'missing-field') {
  throw new Error('broken reference status was not preserved');
}
const payload = parseDatasetFieldDragPayload(
  datasetFieldDragPayload('patients', 'result_value', 'decimal')
);
if (payload.fieldName !== 'result_value'
    || datasetFieldObjectDefaults('decimal').align !== 'right') {
  throw new Error('drag payload or type defaults are incorrect');
}
if (datasetFieldObjectDefaults('binary') !== null
    || datasetFieldObjectDefaults('unknown') !== null) {
  throw new Error('unsupported type policy is not enforced');
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


def test_inspector_exposes_binding_selection_status_and_clear_action() -> None:
    source = (UI_ROOT / "js/inspector.js").read_text(encoding="utf-8")

    assert 'section("Data Binding"' in source
    assert 'name: "dataset_binding.dataset"' in source
    assert 'name: "dataset_binding.field"' in source
    assert 'clear.dataset.inspectorCommand = "clearDatasetBinding"' in source
    assert "datasetFieldBindingStatus" in source
