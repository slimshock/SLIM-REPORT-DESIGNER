from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "packages/slim_report_designer_ui/slim_report_designer_ui/static"


def test_designer_header_rename_is_ui_only_and_data_source_manager_is_present() -> None:
    html = (UI_ROOT / "index.html").read_text(encoding="utf-8")
    toolbar = (UI_ROOT / "js/toolbar.js").read_text(encoding="utf-8")
    designer = (UI_ROOT / "js/designer.js").read_text(encoding="utf-8")

    assert '<span class="brand-mark">SR</span>' in html
    assert "<span>Report Designer</span>" in html
    assert "<span>Slim Report Designer</span>" not in html
    assert "<title>Slim Report Designer</title>" in html
    assert 'id="data-source-modal"' in html
    assert 'type="password"' in html
    assert "Data Sources" in toolbar
    assert 'command === "dataSources"' in designer
    assert "slim_report_designer_ui" not in html


def test_data_source_form_helpers_validate_and_keep_credentials_explicit() -> None:
    module_path = (
        "./packages/slim_report_designer_ui/"
        "slim_report_designer_ui/static/js/data_sources.js"
    )
    script = """
import {
  credentialStatusLabel,
  normalizeDataSourceValues,
  validateDataSourceValues
} from '__MODULE_PATH__';

const base = {
  name: 'Main MySQL', host: 'localhost', port: 3306, database: 'lis',
  username: 'report_user', credentialMode: 'passwordRef', password: '',
  passwordRef: 'MYSQL_PASSWORD', charset: 'utf8mb4', connectTimeout: 10,
  queryTimeout: 30
};
if (Object.keys(validateDataSourceValues(base)).length !== 0) {
  throw new Error('valid values were rejected');
}
const invalid = validateDataSourceValues({ ...base, name: '', port: 70000 });
if (!invalid.name || !invalid.port) {
  throw new Error('required or port validation did not run');
}
const reference = normalizeDataSourceValues(base);
if (reference.password !== null || reference.passwordRef !== 'MYSQL_PASSWORD') {
  throw new Error('reference credential payload was not explicit');
}
const runtime = normalizeDataSourceValues(
  { ...base, credentialMode: 'runtimePassword', passwordRef: '', password: '' },
  'runtime-only'
);
if (runtime.password !== 'runtime-only' || runtime.passwordRef !== null) {
  throw new Error('runtime credential payload was not explicit');
}
const none = normalizeDataSourceValues({ ...base, credentialMode: 'none' });
if (!none.clearRuntimePassword || !none.clearPasswordRef) {
  throw new Error('credential clearing was ambiguous');
}
if (credentialStatusLabel({ passwordRefConfigured: true }) !== 'Environment reference configured') {
  throw new Error('safe credential status is incorrect');
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


def test_data_source_ui_does_not_persist_or_render_passwords_as_metadata() -> None:
    source = (UI_ROOT / "js/data_sources.js").read_text(encoding="utf-8")
    api = (UI_ROOT / "js/api.js").read_text(encoding="utf-8")

    assert "localStorage" not in source
    assert "sessionStorage" not in source
    assert "dataset.password" not in source
    assert "runtimePasswords = new Map()" in source
    assert 'method: "POST"' in api
    assert "JSON.stringify" in api
