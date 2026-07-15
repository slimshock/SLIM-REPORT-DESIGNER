from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "packages/slim_report_designer_ui/slim_report_designer_ui/static"


def test_new_report_entry_point_and_accessible_modal_are_present() -> None:
    html = (UI_ROOT / "index.html").read_text(encoding="utf-8")
    toolbar = (UI_ROOT / "js/toolbar.js").read_text(encoding="utf-8")
    designer = (UI_ROOT / "js/designer.js").read_text(encoding="utf-8")

    assert 'id="new-report-modal"' in html
    assert 'aria-labelledby="new-report-title"' in html
    assert 'role="dialog"' in html
    assert '["newReport", "New Report"' in toolbar
    assert 'command === "newReport"' in designer
    assert 'event.key.toLowerCase() === "n"' in designer
    assert "saveCurrentReport" in designer
    assert "state.undoStack = []" in designer


def test_wizard_helpers_build_safe_configuration_without_runtime_values() -> None:
    module_path = (
        "./packages/slim_report_designer_ui/slim_report_designer_ui/static/js/new_report_wizard.js"
    )
    script = """
import { buildConfiguration, createWizardDraft, friendlyLabel } from '__MODULE_PATH__';

const active = {
  dataSources: [{
    id: 'main', name: 'Main', type: 'mysql',
    connection: { host: 'db', database: 'lis', username: 'reader', passwordRef: 'MYSQL_PW' }
  }]
};
const draft = createWizardDraft(active);
draft.mode = 'mysql';
draft.reportName = 'Orders';
draft.layoutType = 'tabular';
draft.template.dataSources = [structuredClone(active.dataSources[0])];
draft.template.dataSources[0].connection.password = 'runtime-secret';
draft.template.datasets = [{
  id: 'orders', name: 'Orders', dataSourceId: 'main', sourceType: 'query',
  query: 'SELECT id FROM report_orders WHERE day >= :date_from',
  parameters: [{ name: 'date_from', dataType: 'date', required: true }],
  fields: [{ name: 'order_id', dataType: 'integer' }]
}];
draft.fields = draft.template.datasets[0].fields;
draft.selectedFields = new Set(['order_id']);
draft.labels = { order_id: 'Order ID' };
draft.temporaryValues = { date_from: '2026-01-01' };
const configuration = buildConfiguration(draft);
const serialized = JSON.stringify(configuration);
if (serialized.includes('runtime-secret') || serialized.includes('2026-01-01')) {
  throw new Error('secret or temporary values entered final configuration');
}
if (configuration.layout.selectedFields[0].field !== 'order_id') {
  throw new Error('selected field was not preserved');
}
if (friendlyLabel('wbc_result_id') !== 'WBC Result ID') {
  throw new Error('friendly labels do not preserve acronyms');
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


def test_wizard_does_not_persist_draft_or_execute_dataset_rows() -> None:
    source = (UI_ROOT / "js/new_report_wizard.js").read_text(encoding="utf-8")

    assert "localStorage" not in source
    assert "sessionStorage" not in source
    assert "temporaryValues" in source
    assert "buildNewReport" in source
    assert "createViewDataset" in source
    assert "createQueryDataset" in source
    assert "fetchall" not in source
    assert "pymysql" not in source.lower()
