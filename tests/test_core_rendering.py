from __future__ import annotations

import pytest

from slim_report_core import Report, ReportValidationError, render_html, render_pdf
from slim_report_core.expressions import resolve_expression
from slim_report_core.rendering import render_html as render_report_html
from slim_report_core.serialization import JSONSerializer


def test_field_value_resolving_from_nested_data() -> None:
    assert resolve_expression("patient.name", {"patient": {"name": "Juan Dela Cruz"}}) == (
        "Juan Dela Cruz"
    )


def test_html_rendering_contains_expected_patient_name() -> None:
    report = load_report()

    html = render_html(report, sample_data())

    assert "<!doctype html>" in html
    assert "slim-report-page" in html
    assert "Juan Dela Cruz" in html
    assert "width: 816.0px" in html
    assert "height: 1056.0px" in html


def test_html_rendering_keeps_horizontal_lines_visible() -> None:
    report = load_report()

    html = render_html(report, sample_data())

    assert 'data-slim-object="line1"' in html
    assert "top: 130.0px; width: 500.0px; height: 1.0px" in html
    assert 'viewBox="0 0 500.0 1.0"' in html
    assert 'y1="0.5" x2="500.0" y2="0.5"' in html
    assert 'data-slim-object="box1"' in html
    assert "border: 1.0px solid #000000" in html


def test_pdf_rendering_returns_pdf_bytes() -> None:
    report = load_report()

    pdf = render_pdf(report, sample_data())

    assert pdf.startswith(b"%PDF")


def test_missing_field_does_not_crash() -> None:
    report = load_report()

    html = render_html(report, {"patient": {}})

    assert "Juan Dela Cruz" not in html
    assert "<!doctype html>" in html


def test_report_render_html_and_render_pdf_methods() -> None:
    report = load_report()

    assert "Juan Dela Cruz" in report.render_html(sample_data())
    assert report.render_pdf(sample_data()).startswith(b"%PDF")


def test_render_functions_accept_report_domain_model() -> None:
    report = load_report()

    assert "Juan Dela Cruz" in render_html(report, sample_data())
    assert render_pdf(report, sample_data()).startswith(b"%PDF")


def test_public_renderer_rejects_json_mapping() -> None:
    with pytest.raises(ReportValidationError, match="Report domain model"):
        render_html(sample_template(), sample_data())  # type: ignore[arg-type]


def test_low_level_renderer_rejects_json_mapping() -> None:
    with pytest.raises(ReportValidationError, match="Report domain model"):
        render_report_html(sample_template(), sample_data())


def sample_data() -> dict[str, dict[str, str]]:
    return {
        "patient": {
            "name": "Juan Dela Cruz",
        }
    }


def load_report() -> Report:
    return JSONSerializer().load_mapping(sample_template())


def sample_template() -> dict:
    return {
        "version": "1.0",
        "metadata": {
            "title": "Laboratory Result",
            "description": None,
            "author": None,
            "tags": [],
            "custom": {},
        },
        "page": {
            "size": "letter",
            "orientation": "portrait",
            "unit": "px",
        },
        "objects": [
            {
                "id": "title1",
                "type": "text",
                "x": 50,
                "y": 40,
                "width": 400,
                "height": 30,
                "text": "Laboratory Result",
                "style": {
                    "font_size": 18,
                    "bold": True,
                },
            },
            {
                "id": "patient_name",
                "type": "field",
                "x": 50,
                "y": 90,
                "width": 300,
                "height": 20,
                "binding": "patient.name",
                "style": {
                    "font_size": 12,
                },
            },
            {
                "id": "line1",
                "type": "line",
                "x": 50,
                "y": 130,
                "width": 500,
                "height": 0,
                "style": {
                    "stroke_width": 1,
                },
            },
            {
                "id": "box1",
                "type": "rectangle",
                "x": 50,
                "y": 150,
                "width": 500,
                "height": 100,
                "style": {
                    "border_width": 1,
                },
            },
        ],
        "bands": [],
        "assets": [],
    }
