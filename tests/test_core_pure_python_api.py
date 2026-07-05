from __future__ import annotations

from pathlib import Path

import pytest

from slim_report_core import ExporterError, Report, ReportObject
from slim_report_core.serialization import JSONSerializer


def test_report_load_json_and_render_html(tmp_path: Path) -> None:
    report = Report()
    report.add_object(
        ReportObject(
            id="title",
            type="text",
            x=1,
            y=1,
            width=3,
            height=0.5,
            properties={"text": "Patient: {{ patient.name }}"},
        )
    )
    template_path = tmp_path / "template.json"
    serializer = JSONSerializer()
    serializer.save(report, template_path)

    loaded = serializer.load(template_path)
    html = loaded.render({"patient": {"name": "Iris"}}, exporter="html")

    assert isinstance(html, str)
    assert "Patient: Iris" in html


def test_report_save_html(tmp_path: Path) -> None:
    report = Report()
    report.add_object(
        ReportObject(
            id="title",
            type="text",
            properties={"text": "Hello {{ name }}"},
        )
    )
    output_path = tmp_path / "output.html"

    report.save_html(output_path, {"name": "Nora"})

    assert "Hello Nora" in output_path.read_text(encoding="utf-8")


def test_report_render_rejects_unknown_exporter() -> None:
    report = Report()

    with pytest.raises(ExporterError):
        report.render({}, exporter="missing")
