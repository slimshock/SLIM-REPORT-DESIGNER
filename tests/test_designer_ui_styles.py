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
