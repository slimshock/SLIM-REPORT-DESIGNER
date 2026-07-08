from __future__ import annotations

import subprocess
from pathlib import Path


def test_designer_history_uses_local_storage_and_limits_versions() -> None:
    module_path = (
        "./packages/slim_report_designer_ui/"
        "slim_report_designer_ui/static/js/history.js"
    )
    script = """
globalThis.localStorage = {
  data: new Map(),
  getItem(key) { return this.data.has(key) ? this.data.get(key) : null; },
  setItem(key, value) { this.data.set(key, value); },
  removeItem(key) { this.data.delete(key); }
};

const history = await import('__MODULE_PATH__');
const template = { metadata: { name: 'Demo' }, objects: [{ id: 'a' }] };

if (history.getHistoryKey('cerebro cbc') !== 'slim_report_designer.history.cerebro_cbc') {
  throw new Error('history key was not sanitized');
}

for (let index = 0; index < 22; index += 1) {
  history.createVersion('demo', template, `Version ${index}`);
}

const versions = history.listVersions('demo');
if (versions.length !== 20 || versions[0].label !== 'Version 21') {
  throw new Error('history limit was not enforced');
}

const restored = history.restoreVersion('demo', versions[0].id);
if (!restored || restored.objects.length !== 1) {
  throw new Error('version was not restored');
}

history.deleteVersion('demo', versions[0].id);
if (history.listVersions('demo').length !== 19) {
  throw new Error('version was not deleted');
}

history.clearVersions('demo');
if (history.listVersions('demo').length !== 0) {
  throw new Error('history was not cleared');
}
""".replace("__MODULE_PATH__", module_path)

    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
