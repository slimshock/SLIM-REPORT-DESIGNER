from __future__ import annotations

import builtins

import pytest

from slim_report_core import (
    ExporterError,
    HTMLExporter,
    PDFExporter,
    Report,
    ReportObject,
    WidgetRegistry,
    WidgetValidationError,
)
from slim_report_core.exporters import create_default_exporter_registry
from slim_report_core.widgets import (
    ImageWidget,
    RectangleWidget,
    TextWidget,
    create_default_widget_registry,
)


def test_default_widget_registry_contains_builtin_widgets() -> None:
    registry = create_default_widget_registry()

    assert registry.list() == ["field", "image", "line", "rectangle", "text"]
    assert registry.get("text") is not None
    assert registry.get("field") is not None
    assert registry.get("image") is not None
    assert registry.get("line") is not None
    assert registry.get("rectangle") is not None


def test_widget_registry_validates_widget_type() -> None:
    class BrokenWidget(TextWidget):
        type = ""

    registry = WidgetRegistry()

    with pytest.raises(WidgetValidationError):
        registry.register(BrokenWidget())


def test_text_widget_renders_resolved_and_escaped_html() -> None:
    widget = TextWidget()
    obj = ReportObject(
        id="message",
        type="text",
        width=144,
        height=24,
        properties={"text": "Hello {{ patient.name }}", "font_size": 12},
    )

    html = widget.render_html(obj, {"patient": {"name": "<Ana>"}}, {})

    assert "Hello &lt;Ana&gt;" in html
    assert "position: absolute" in html
    assert "font-size: 12.0pt" in html


def test_widget_validate_rejects_wrong_type() -> None:
    widget = RectangleWidget()
    obj = ReportObject(id="message", type="text")

    with pytest.raises(WidgetValidationError):
        widget.validate(obj)


def test_image_widget_renders_blank_without_source() -> None:
    widget = ImageWidget()
    obj = ReportObject(id="logo", type="image", width=80, height=40)

    html = widget.render_html(obj, {}, {})

    assert ">Image<" not in html
    assert 'data-slim-object="logo"' in html


def test_html_exporter_renders_absolute_positioned_report() -> None:
    report = Report()
    report.template.metadata.title = "Patient Report"
    report.add_object(
        ReportObject(
            id="title",
            type="text",
            x=1,
            y=1,
            width=3,
            height=0.4,
            properties={"text": "Patient: {{ patient.name }}"},
        )
    )
    report.add_object(
        ReportObject(
            id="result",
            type="field",
            x=1,
            y=1.5,
            width=3,
            height=0.4,
            properties={"field": "result.HGB"},
        )
    )
    report.add_object(ReportObject(id="rule", type="line", x=1, y=2, width=4, height=0))
    report.add_object(ReportObject(id="box", type="rectangle", x=1, y=2.5, width=4, height=1))
    report.add_object(ReportObject(id="logo", type="image", x=1, y=4, width=1, height=1))

    html = HTMLExporter().export(
        report,
        data={"patient": {"name": "Mina"}, "result": {"HGB": 12.8}},
    )

    assert '<div class="slim-report-page"' in html
    assert "width: 816.0px" in html
    assert "height: 1056.0px" in html
    assert "Patient: Mina" in html
    assert ">12.8<" in html
    assert "<svg" in html
    assert 'data-slim-object="box"' in html
    assert 'data-slim-object="logo"' in html


def test_html_exporter_supports_a4_landscape() -> None:
    report = Report()
    html = HTMLExporter(page_size="a4", orientation="landscape").export(report)

    assert "width: 1122.5196850393702px" in html
    assert "height: 793.7007874015749px" in html


def test_html_exporter_rejects_unknown_widget_type() -> None:
    report = Report()
    report.add_object(ReportObject(id="unknown", type="unknown"))

    with pytest.raises(ExporterError):
        HTMLExporter().export(report)


def test_default_exporter_registry_exports_html() -> None:
    report = Report()
    registry = create_default_exporter_registry()

    assert registry.list() == ["html", "pdf"]
    assert "<!doctype html>" in registry.export("html", report)


def test_pdf_exporter_requires_reportlab_when_not_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = Report()
    real_import = builtins.__import__

    def fake_import(name: str, *args, **kwargs):
        if name.startswith("reportlab"):
            raise ImportError("ReportLab intentionally hidden for test")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(ExporterError, match="ReportLab"):
        PDFExporter().export(report)
