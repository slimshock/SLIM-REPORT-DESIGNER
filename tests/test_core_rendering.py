from __future__ import annotations

from pathlib import Path

import pytest

from slim_report_core import Band, Report, ReportValidationError, render_html, render_pdf
from slim_report_core.expressions import resolve_expression
from slim_report_core.rendering import render_html as render_report_html
from slim_report_core.rendering.context import create_render_context
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
    assert "width: 612.0px" in html
    assert "height: 792.0px" in html


def test_html_rendering_keeps_horizontal_lines_visible() -> None:
    report = load_report()

    html = render_html(report, sample_data())

    assert 'data-slim-object="line1"' in html
    assert "top: 130.0px; width: 500.0px; height: 1.0px" in html
    assert 'viewBox="0 0 500.0 1.0"' in html
    assert 'y1="0.5" x2="500.0" y2="0.5"' in html
    assert 'data-slim-object="box1"' in html
    assert "border: 2.0px solid #654321" in html


def test_html_rendering_applies_extended_style_fields() -> None:
    html = render_html(load_report(), sample_data())

    assert "font-family: Courier" in html
    assert "font-style: italic" in html
    assert "text-decoration: underline" in html
    assert "background: #ffeecc" in html
    assert "text-align: center" in html
    assert "align-items: center" in html
    assert 'stroke="#123456"' in html
    assert "border: 2.0px solid #654321" in html
    assert "background: #eeeeee" in html
    assert 'data-slim-object="logo"' in html
    assert "object-fit: contain" in html


def test_render_context_applies_shared_style_defaults() -> None:
    report = JSONSerializer().load_mapping(
        {
            "version": "1.0",
            "metadata": {"title": "Defaults"},
            "page": {"size": "A4", "orientation": "portrait", "unit": "px"},
            "objects": [
                {
                    "id": "plain_text",
                    "type": "text",
                    "x": 10,
                    "y": 10,
                    "width": 100,
                    "height": 20,
                    "text": "Plain",
                },
                {
                    "id": "plain_line",
                    "type": "line",
                    "x": 10,
                    "y": 40,
                    "width": 100,
                    "height": 0,
                },
            ],
            "bands": [],
            "assets": [],
        }
    )

    context = create_render_context(report)

    assert context.page.width_px == 595.0
    assert context.page.height_px == 842.0
    text_style = context.objects[0].style
    line_style = context.objects[1].style
    assert text_style["font_family"] == "Arial"
    assert text_style["font_size"] == 12
    assert text_style["line_height"] == 1.2
    assert text_style["color"] == "#111827"
    assert line_style["stroke_width"] == 1
    assert line_style["stroke_color"] == "#111827"


def test_render_context_preserves_explicit_style_fields() -> None:
    report = load_report()

    context = create_render_context(report)

    title_style = context.objects[0].style
    assert title_style["font_family"] == "Courier"
    assert title_style["font_size"] == 18
    assert title_style["bold"] is True
    assert title_style["italic"] is True
    assert title_style["underline"] is True
    assert title_style["align"] == "center"


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


def test_sample_templates_render_html_and_pdf() -> None:
    for template_name in ("cerebro_cbc", "lab_result"):
        report = JSONSerializer().load(REPO_ROOT / f"examples/flask_app/sample_templates/{template_name}.json")

        html = render_html(report, sample_data())
        pdf = render_pdf(report, sample_data())

        assert "<!doctype html>" in html
        assert "slim-report-page" in html
        assert len(html) > 1000
        assert pdf.startswith(b"%PDF")
        assert len(pdf) > 1000


def test_banded_template_renders_band_backgrounds_html_and_pdf() -> None:
    report = Report(
        page={"width": 595, "height": 842, "unit": "px"},
        bands=[
            Band(
                id="page_header",
                type="page_header",
                name="Page Header",
                y=0,
                height=100,
                background_color="#eeeeee",
            ),
            Band(id="detail", type="detail", name="Detail", y=100, height=682),
            Band(
                id="page_footer",
                type="page_footer",
                name="Page Footer",
                y=782,
                height=60,
                background_color="#dddddd",
            ),
        ],
    )
    report.page().text("Header", id="header", x=20, y=20, width=120, height=24)
    report.objects[0].band_id = "page_header"

    html = render_html(report, {})
    pdf = render_pdf(report, {})

    assert 'data-slim-band="page_header"' in html
    assert "background: #eeeeee" in html
    assert "Header" in html
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000


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


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_report() -> Report:
    return JSONSerializer().load_mapping(sample_template())


def sample_template() -> dict:
    svg_data_url = (
        "data:image/svg+xml;base64,"
        "PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxIiBoZWlnaHQ9IjEiLz4="
    )
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
            "background_color": "#ffffff",
            "transparent": False,
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
                    "font_family": "Courier",
                    "font_size": 18,
                    "bold": True,
                    "italic": True,
                    "underline": True,
                    "color": "#005577",
                    "background_color": "#ffeecc",
                    "align": "center",
                    "vertical_align": "middle",
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
                    "stroke_color": "#123456",
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
                    "border_width": 2,
                    "border_color": "#654321",
                    "background_color": "#eeeeee",
                },
            },
            {
                "id": "logo",
                "type": "image",
                "x": 50,
                "y": 270,
                "width": 40,
                "height": 40,
                "src": svg_data_url,
                "alt": "Logo",
                "style": {
                    "object_fit": "contain",
                    "border_width": 1,
                    "border_color": "#000000",
                },
            },
        ],
        "bands": [],
        "assets": [],
    }
