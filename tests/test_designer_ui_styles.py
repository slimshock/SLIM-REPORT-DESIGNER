from __future__ import annotations

import subprocess
from pathlib import Path


def test_canvas_delete_shortcut_does_not_use_backspace() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "packages/slim_report_designer_ui/slim_report_designer_ui/static/js/canvas.js"
    ).read_text(encoding="utf-8")

    assert 'event.key === "Delete"' in source
    assert "Backspace" not in source


def test_inspector_alignment_controls_use_icons() -> None:
    inspector_source = (
        Path(__file__).resolve().parents[1]
        / "packages/slim_report_designer_ui/slim_report_designer_ui/static/js/inspector.js"
    ).read_text(encoding="utf-8")
    icons_source = (
        Path(__file__).resolve().parents[1]
        / "packages/slim_report_designer_ui/slim_report_designer_ui/static/js/icons.js"
    ).read_text(encoding="utf-8")

    for icon_name in [
        "align-left",
        "align-center",
        "align-right",
        "align-top",
        "align-middle",
        "align-bottom",
    ]:
        assert icon_name in inspector_source
        assert icon_name in icons_source

    assert "button.innerHTML" in inspector_source
    assert "sr-only" in inspector_source


def test_canvas_settings_helpers() -> None:
    module_path = (
        "./packages/slim_report_designer_ui/"
        "slim_report_designer_ui/static/js/canvas_settings.js"
    )
    script = """
import {
  defaultCanvasSettings,
  gridSizeForUnit,
  normalizeCanvasSettings,
  screenDeltaToRealDelta,
  snapValue,
  zoomIn,
  zoomOut,
  zoomPercent
} from '__MODULE_PATH__';

const defaults = defaultCanvasSettings();
if (defaults.zoom !== 1 || defaults.grid_size !== 10) {
  throw new Error('canvas defaults invalid');
}
if (!defaults.show_grid || !defaults.snap_to_grid) {
  throw new Error('canvas boolean defaults invalid');
}
if (snapValue(14, 10) !== 10 || snapValue(16, 10) !== 20) {
  throw new Error('snap helper invalid');
}
if (screenDeltaToRealDelta(50, 2) !== 25) {
  throw new Error('zoom delta helper invalid');
}
if (gridSizeForUnit({ grid_size: 10 }, 2) !== 5) {
  throw new Error('grid unit helper invalid');
}
if (zoomIn(1) !== 1.25 || zoomOut(1) !== 0.75 || zoomPercent(1.25) !== '125%') {
  throw new Error('zoom step helper invalid');
}

const normalized = normalizeCanvasSettings({
  zoom: 99,
  grid_size: -5,
  show_grid: false,
  snap_to_grid: false
});
if (normalized.zoom !== 2 || normalized.grid_size !== 1) {
  throw new Error('canvas settings clamp invalid');
}
if (normalized.show_grid || normalized.snap_to_grid) {
  throw new Error('canvas settings boolean normalization invalid');
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


def test_data_field_helpers_infer_nested_and_array_paths() -> None:
    module_path = (
        "./packages/slim_report_designer_ui/"
        "slim_report_designer_ui/static/js/data_fields.js"
    )
    script = """
import {
  fieldExists,
  flattenDataPaths,
  getArrayChildFields,
  getFieldValue,
  getArrayByPath,
  getRowValue,
  inferFieldsFromSample,
  normalizeFieldPath
} from '__MODULE_PATH__';

const sample = {
  patient: { name: 'Juan Dela Cruz', age: '34' },
  order: { id: 'ORD-0001' },
  results: [{ name: 'HGB', value: '13.2' }]
};

const paths = flattenDataPaths(sample);
const expectedPaths = [
  'patient.name',
  'patient.age',
  'order.id',
  'results[0].name',
  'results[].value'
];
for (const path of expectedPaths) {
if (!paths.includes(path)) {
    throw new Error(`missing path ${path}`);
  }
}
if (!paths.includes('results[]')) {
  throw new Error('array root path missing');
}

const fields = inferFieldsFromSample(sample);
if (!fields.some((field) => field.path === 'patient.name' && field.sample === 'Juan Dela Cruz')) {
  throw new Error('field inference failed');
}
if (getFieldValue(sample, 'results[].value') !== '13.2') {
  throw new Error('array field lookup failed');
}
if (getArrayByPath(sample, 'results').length !== 1) {
  throw new Error('array path lookup failed');
}
if (getRowValue(sample.results[0], 'results[].value', 'results') !== '13.2') {
  throw new Error('row value lookup failed');
}
if (getFieldValue(sample, 'patient.missing') !== undefined) {
  throw new Error('missing path should be undefined');
}
if (normalizeFieldPath('{{ patient.name }}') !== 'patient.name') {
  throw new Error('field path normalization failed');
}
if (!fieldExists({ data: { fields } }, 'patient.name')) {
  throw new Error('field existence check failed');
}
const childFields = getArrayChildFields({ data: { fields } }, 'results');
if (
  childFields.length !== 2 ||
  childFields[0].child_path !== 'name' ||
  childFields[1].child_path !== 'value'
) {
  throw new Error('array child field helper failed');
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


def test_designer_normalization_and_save_preserve_template_data() -> None:
    objects_module_path = (
        "./packages/slim_report_designer_ui/"
        "slim_report_designer_ui/static/js/objects.js"
    )
    api_module_path = (
        "./packages/slim_report_designer_ui/"
        "slim_report_designer_ui/static/js/api.js"
    )
    script = """
import { normalizeTemplate } from '__OBJECTS_MODULE_PATH__';
import { previewTemplate, saveTemplate } from '__API_MODULE_PATH__';

const template = normalizeTemplate({
  version: '0.1',
  metadata: { name: 'Repeating' },
  page: { width: 595, height: 842, unit: 'px' },
  bands: [{
    id: 'detail',
    type: 'detail',
    repeat: { enabled: true, data_path: 'results', row_height: 24 }
  }],
  objects: [{ id: 'result_test', type: 'field', binding: 'test', band: 'detail' }],
  data: { sample: { results: [{ test: 'WBC', result: '7.10' }] } },
  assets: []
});

const hasResultsField = template.data.fields.some((field) => field.path === 'results[].test');
if (!template.data.sample.results || !hasResultsField) {
  throw new Error('normalizeTemplate did not preserve or infer data metadata');
}

global.window = {
  SLIM_REPORT_API_BASE: '/report-designer/api',
  SLIM_REPORT_TEMPLATE_ID: 'repeating_lab_result',
  location: { search: '?template=repeating_lab_result' },
  open: () => {}
};
global.URL = { createObjectURL: () => 'blob:preview', revokeObjectURL: () => {} };

let savedBody = null;
global.fetch = async (_url, options) => {
  savedBody = JSON.parse(options.body);
  return { ok: true, json: async () => ({ ok: true }) };
};
const saved = await saveTemplate(template);
if (!saved.data.sample.results || saved.data.fields.length === 0) {
  throw new Error('saveTemplate replaced current template with partial response');
}
if (!savedBody.data.sample.results) {
  throw new Error('saveTemplate did not post data metadata');
}

let previewBody = null;
global.fetch = async (_url, options) => {
  previewBody = JSON.parse(options.body);
  return { ok: true, text: async () => '<!doctype html>' };
};
await previewTemplate(template);
if (!previewBody.template.data.sample.results || previewBody.data.results[0].test !== 'WBC') {
  throw new Error('previewTemplate did not post full template and render data');
}
""".replace("__OBJECTS_MODULE_PATH__", objects_module_path).replace(
        "__API_MODULE_PATH__",
        api_module_path,
    )

    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_designer_static_ui_includes_canvas_controls() -> None:
    toolbar_source = (
        Path(__file__).resolve().parents[1]
        / "packages/slim_report_designer_ui/slim_report_designer_ui/static/js/toolbar.js"
    ).read_text(encoding="utf-8")
    index_source = (
        Path(__file__).resolve().parents[1]
        / "packages/slim_report_designer_ui/slim_report_designer_ui/static/index.html"
    ).read_text(encoding="utf-8")

    assert "zoomOut" in toolbar_source
    assert "fitPage" in toolbar_source
    assert "snap_to_grid" in toolbar_source
    assert "show_grid" in toolbar_source
    assert "undo" in toolbar_source
    assert "redo" in toolbar_source
    assert "canvas-zoom-shell" in index_source


def test_designer_exposes_undo_redo_history_hooks() -> None:
    designer_source = (
        Path(__file__).resolve().parents[1]
        / "packages/slim_report_designer_ui/slim_report_designer_ui/static/js/designer.js"
    ).read_text(encoding="utf-8")
    canvas_source = (
        Path(__file__).resolve().parents[1]
        / "packages/slim_report_designer_ui/slim_report_designer_ui/static/js/canvas.js"
    ).read_text(encoding="utf-8")
    icons_source = (
        Path(__file__).resolve().parents[1]
        / "packages/slim_report_designer_ui/slim_report_designer_ui/static/js/icons.js"
    ).read_text(encoding="utf-8")

    assert "undoStack" in designer_source
    assert "redoStack" in designer_source
    assert "function undo()" in designer_source
    assert "function redo()" in designer_source
    assert "ctrlKey || event.metaKey" in designer_source
    assert "onCaptureHistory" in canvas_source
    assert "onCommitHistory" in canvas_source
    assert "undo:" in icons_source
    assert "redo:" in icons_source


def test_designer_exposes_multi_select_layout_tools() -> None:
    designer_source = (
        Path(__file__).resolve().parents[1]
        / "packages/slim_report_designer_ui/slim_report_designer_ui/static/js/designer.js"
    ).read_text(encoding="utf-8")
    canvas_source = (
        Path(__file__).resolve().parents[1]
        / "packages/slim_report_designer_ui/slim_report_designer_ui/static/js/canvas.js"
    ).read_text(encoding="utf-8")
    toolbar_source = (
        Path(__file__).resolve().parents[1]
        / "packages/slim_report_designer_ui/slim_report_designer_ui/static/js/toolbar.js"
    ).read_text(encoding="utf-8")
    inspector_source = (
        Path(__file__).resolve().parents[1]
        / "packages/slim_report_designer_ui/slim_report_designer_ui/static/js/inspector.js"
    ).read_text(encoding="utf-8")

    for token in [
        "selectedIds",
        "primarySelectedId",
        "alignSelected",
        "distributeSelected",
        "reorderSelected",
        "setLockedSelected",
    ]:
        assert token in designer_source

    assert "selection-bounds" in canvas_source
    assert "primary-selected" in canvas_source
    assert "lock-indicator" in canvas_source
    assert "movingObjects" in canvas_source
    assert "renderMultiSelectionInspector" in inspector_source
    assert "data-inspector-command" in inspector_source
    assert "alignLeft" in toolbar_source
    assert "distributeHorizontal" in toolbar_source
    assert "bringToFront" in toolbar_source
    assert "lockSelected" in toolbar_source


def test_inspector_live_input_preserves_focus() -> None:
    inspector_source = (
        Path(__file__).resolve().parents[1]
        / "packages/slim_report_designer_ui/slim_report_designer_ui/static/js/inspector.js"
    ).read_text(encoding="utf-8")
    designer_source = (
        Path(__file__).resolve().parents[1]
        / "packages/slim_report_designer_ui/slim_report_designer_ui/static/js/designer.js"
    ).read_text(encoding="utf-8")

    assert "preserveInspector" in inspector_source
    assert "shouldPreserveInspectorFocus" in inspector_source
    assert "options.preserveInspector" in designer_source
    assert "inspector.render();" in designer_source


def test_designer_object_style_defaults_and_explicit_values() -> None:
    module_path = (
        "./packages/slim_report_designer_ui/"
        "slim_report_designer_ui/static/js/objects.js"
    )
    script = """
import { normalizeObject, objectStyle, setObjectStyleValue } from '__MODULE_PATH__';

const text = normalizeObject({ id: 'title', type: 'text', text: 'Hello' });
const defaults = objectStyle(text);
if (defaults.font_family !== 'Arial' || defaults.color !== '#111827') {
  throw new Error('text defaults missing');
}
if (defaults.vertical_align !== 'top') {
  throw new Error('vertical alignment default missing');
}
if (text.style && text.style.color) {
  throw new Error('defaults should not be written as explicit style');
}

setObjectStyleValue(text, 'color', '#ff0000');
setObjectStyleValue(text, 'vertical_align', 'middle');
const styled = objectStyle(text);
if (styled.color !== '#ff0000' || text.properties.style.color !== '#ff0000') {
  throw new Error('explicit style was not preserved');
}
if (styled.vertical_align !== 'middle') {
  throw new Error('vertical alignment style was not preserved');
}

const line = normalizeObject({
  id: 'rule',
  type: 'line',
  style: { stroke_color: '#123456', stroke_width: 3 }
});
const lineStyle = objectStyle(line);
if (lineStyle.stroke_color !== '#123456' || lineStyle.stroke_width !== 3) {
  throw new Error('line style was not preserved');
}

const locked = normalizeObject({
  id: 'locked_title',
  type: 'text',
  locked: true,
  text: 'Locked'
});
if (!locked.locked || locked.properties.locked !== true) {
  throw new Error('locked state was not preserved');
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


def test_designer_page_and_image_defaults_roundtrip() -> None:
    module_path = (
        "./packages/slim_report_designer_ui/"
        "slim_report_designer_ui/static/js/objects.js"
    )
    script = """
import {
  createObject,
  normalizeTemplate,
  objectStyle,
  setPageOrientation,
  setPageSize,
  setPageUnit
} from '__MODULE_PATH__';

const template = normalizeTemplate({
  metadata: { name: 'Page Test' },
  page: { size: 'Letter', orientation: 'portrait' },
  objects: [
    {
      id: 'logo',
      type: 'image',
      x: 10,
      y: 20,
      width: 120,
      height: 80,
      src: 'data:image/png;base64,abc',
      style: { object_fit: 'cover', opacity: 0.5 }
    }
  ]
});
if (template.page.unit !== 'px' || template.page.background_color !== '#ffffff') {
  throw new Error('page defaults missing');
}
if (template.objects[0].src !== 'data:image/png;base64,abc') {
  throw new Error('image src was not preserved');
}
if (objectStyle(template.objects[0]).object_fit !== 'cover') {
  throw new Error('image style was not preserved');
}

setPageUnit(template, 'mm');
setPageSize(template, 'A4');
if (template.page.width !== 210 || template.page.height !== 297) {
  throw new Error('A4 mm dimensions were not applied');
}
setPageOrientation(template, 'landscape');
if (template.page.width !== 297 || template.page.height !== 210) {
  throw new Error('landscape dimensions were not applied');
}

const created = createObject('image', template);
if (created.type !== 'image' || created.width !== 120 || created.height !== 80) {
  throw new Error('image defaults invalid');
}
if (objectStyle(created).object_fit !== 'contain') {
  throw new Error('image default style invalid');
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


def test_designer_table_defaults_and_column_generation() -> None:
    module_path = (
        "./packages/slim_report_designer_ui/"
        "slim_report_designer_ui/static/js/objects.js"
    )
    script = """
import { createObject, generateTableColumns, normalizeTemplate } from '__MODULE_PATH__';

const template = normalizeTemplate({
  metadata: { name: 'Table Test' },
  page: { width: 595, height: 842, unit: 'px' },
  objects: [],
  bands: [{ id: 'detail', type: 'detail', y: 0, height: 842 }],
  data: {
    sample: { results: [{ test: 'WBC', result: '7.10', unit: '10^9/L' }] }
  },
  assets: []
});

const table = createObject('table', template);
if (table.type !== 'table' || table.width !== 500 || table.height !== 220) {
  throw new Error('table defaults invalid');
}
if (table.data_path !== 'results') {
  throw new Error('table did not select first array data path');
}
if (!table.columns.some((column) => column.binding === 'test')) {
  throw new Error('table columns were not inferred');
}
table.columns = [];
table.properties.columns = [];
generateTableColumns(template, table);
if (table.columns.length < 3 || table.columns[1].binding !== 'result') {
  throw new Error('table column generation failed');
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


def test_designer_barcode_and_qrcode_defaults() -> None:
    module_path = (
        "./packages/slim_report_designer_ui/"
        "slim_report_designer_ui/static/js/objects.js"
    )
    script = """
import { createObject, normalizeTemplate, objectStyle } from '__MODULE_PATH__';

const template = normalizeTemplate({
  metadata: { name: 'Barcode Test' },
  page: { width: 595, height: 842, unit: 'px' },
  objects: [],
  bands: [{ id: 'detail', type: 'detail', y: 0, height: 842 }],
  data: {
    fields: [
      { path: 'patient.name', label: 'Patient Name', type: 'string' },
      { path: 'order.id', label: 'Order ID', type: 'string' }
    ],
    sample: { order: { id: 'ORDER-1001' } }
  },
  assets: []
});

const barcode = createObject('barcode', template);
if (barcode.type !== 'barcode' || barcode.width !== 160 || barcode.height !== 48) {
  throw new Error('barcode defaults invalid');
}
if (barcode.binding !== 'order.id' || barcode.format !== 'code128' || !barcode.show_text) {
  throw new Error('barcode binding or settings invalid');
}
if (objectStyle(barcode).foreground_color !== '#111827') {
  throw new Error('barcode style invalid');
}

const qrcode = createObject('qrcode', template);
if (qrcode.type !== 'qrcode' || qrcode.width !== 80 || qrcode.height !== 80) {
  throw new Error('qrcode defaults invalid');
}
if (qrcode.binding !== 'order.id' || qrcode.error_correction !== 'M') {
  throw new Error('qrcode binding or settings invalid');
}
if (objectStyle(qrcode).background_color !== '#ffffff') {
  throw new Error('qrcode style invalid');
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


def test_designer_qrcode_preview_uses_centered_square_content() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "packages/slim_report_designer_ui/slim_report_designer_ui/static/js/canvas.js"
    ).read_text(encoding="utf-8")
    css = (
        Path(__file__).resolve().parents[1]
        / "packages/slim_report_designer_ui/slim_report_designer_ui/static/css/designer.css"
    ).read_text(encoding="utf-8")

    assert "const qrSize = Math.max(Math.min(Number(object.width)" in source
    assert "const qrX = Math.max(((Number(object.width)" in source
    assert "const qrY = Math.max(((Number(object.height)" in source
    assert "appendQrSvg(wrapper" in source
    assert ".qrcode-preview {\n  position: relative;" in css
    assert ".qrcode-grid {\n  position: absolute;" in css
    qrcode_css = css[css.index(".qrcode-grid {") : css.index(".inspector-form {")]
    assert "background-image:" not in qrcode_css


def test_designer_band_helpers_normalize_and_clamp_objects() -> None:
    module_path = (
        "./packages/slim_report_designer_ui/"
        "slim_report_designer_ui/static/js/objects.js"
    )
    script = """
import {
  assignObjectBand,
  clampObjectToBand,
  createDefaultTemplate,
  normalizeTemplate,
  setBandValue,
  setObjectBand
} from '__MODULE_PATH__';

const oldTemplate = normalizeTemplate({
  metadata: { name: 'Old' },
  page: { width: 500, height: 700, unit: 'px' },
  objects: [{ id: 'title', type: 'text', y: 20, width: 100, height: 20 }],
  bands: []
});
if (oldTemplate.bands.length !== 1 || oldTemplate.bands[0].id !== 'detail') {
  throw new Error('old template did not receive compatibility detail band');
}
if (oldTemplate.objects[0].band !== 'detail') {
  throw new Error('old object did not default to detail band');
}

const blank = createDefaultTemplate();
if (blank.bands.length !== 3 || blank.bands[0].id !== 'page_header') {
  throw new Error('blank template did not receive default report bands');
}
const object = {
  id: 'footer_text',
  type: 'text',
  x: 10,
  y: 0,
  width: 100,
  height: 20,
  properties: {}
};
assignObjectBand(blank, object, 'page_footer');
clampObjectToBand(blank, object);
if (object.band !== 'page_footer' || object.y < blank.bands[2].y) {
  throw new Error('object was not clamped into footer band');
}
setObjectBand(blank, object, 'page_header');
if (object.band !== 'page_header' || object.y >= blank.bands[1].y) {
  throw new Error('object band change did not clamp into header');
}
setBandValue(blank, 'page_header', 'height', 120);
const expectedFooterY = blank.bands[0].height + blank.bands[1].height;
if (blank.bands[1].y !== 120 || blank.bands[2].y !== expectedFooterY) {
  throw new Error('band layout was not recalculated');
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
