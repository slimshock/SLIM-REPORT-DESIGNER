from __future__ import annotations

from pathlib import Path

import pytest

from slim_report_core import Band, Report, ReportValidationError, render_html, render_pdf
from slim_report_core.expressions import resolve_expression
from slim_report_core.rendering import render_html as render_report_html
from slim_report_core.rendering.context import (
    RenderObject,
    apply_conditional_styles,
    create_render_context,
    resolve_binding,
)
from slim_report_core.rendering.pagination import (
    calculate_rows_per_page,
    get_available_detail_height,
    group_rows,
    pagination_summary,
    sort_groups,
)
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
    assert "@page { size:" in html
    assert "print-color-adjust: exact" in html
    assert ".slim-report-preview-toolbar" in html
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


def test_html_rendering_expands_repeating_detail_rows() -> None:
    report = repeating_report()

    html = render_html(report, repeating_data())

    assert "WBC" in html
    assert "7.10" in html
    assert "HGB" in html
    assert "14.20" in html
    assert "top: 152.0px" in html
    assert "top: 176.0px" in html
    assert "LAB RESULT" in html
    assert html.count("LAB RESULT") == 1


def test_conditional_style_merge_and_hide_action() -> None:
    obj = RenderObject(
        id="row_result",
        type="field",
        x=0,
        y=0,
        width=80,
        height=18,
        binding="result",
        style={"font_size": 10, "color": "#111827", "bold": False},
        conditions=[
            {
                "id": "high",
                "enabled": True,
                "condition": "flag == 'H'",
                "style": {"color": "#dc2626", "bold": True},
            },
            {
                "id": "large",
                "enabled": True,
                "condition": "numeric_value > 10",
                "style": {"background_color": "#fee2e2", "color": "#991b1b"},
            },
            {
                "id": "hidden",
                "enabled": True,
                "condition": "result == ''",
                "style": {},
                "action": "hide",
            },
        ],
    )

    normal = apply_conditional_styles(
        obj,
        {"__slim_row__": {"flag": "N", "numeric_value": 7, "result": "7"}},
    )
    high = apply_conditional_styles(
        obj,
        {"__slim_row__": {"flag": "H", "numeric_value": 12, "result": "12"}},
    )
    hidden = apply_conditional_styles(
        obj,
        {"__slim_row__": {"flag": "N", "numeric_value": 0, "result": ""}},
    )

    assert normal["style"] == obj.style
    assert normal["hidden"] is False
    assert high["style"]["font_size"] == 10
    assert high["style"]["bold"] is True
    assert high["style"]["color"] == "#991b1b"
    assert high["style"]["background_color"] == "#fee2e2"
    assert hidden["hidden"] is True


def test_pagination_helpers_calculate_detail_capacity() -> None:
    context = create_render_context(repeating_report(), repeating_data())

    assert get_available_detail_height(context) == 680
    assert calculate_rows_per_page(24, 96) == 4
    assert calculate_rows_per_page(24, 0) == 1


def test_html_rendering_paginates_repeating_detail_rows() -> None:
    report = repeating_report()

    html = render_html(report, many_repeating_data())
    summary = pagination_summary(create_render_context(report), many_repeating_data())

    assert summary.page_count > 1
    assert summary.repeated_row_count == 36
    assert html.count('class="slim-report-page"') == summary.page_count
    assert html.count("LAB RESULT") == summary.page_count
    assert "Nitrite" in html
    assert 'data-slim-object="page_index"' in html
    assert 'data-slim-object="page_count"' in html
    assert f">{summary.page_count}</div>" in html


def test_grouping_helpers_group_preserve_order_and_sort() -> None:
    rows = [
        {"section": "HEMATOLOGY", "test": "WBC"},
        {"section": "HEMATOLOGY", "test": "HGB"},
        {"section": "CHEMISTRY", "test": "FBS"},
        {"test": "No Section"},
    ]

    groups = group_rows(rows, "section")

    assert [group.key for group in groups] == ["HEMATOLOGY", "CHEMISTRY", ""]
    assert [row["test"] for row in groups[0].rows] == ["WBC", "HGB"]
    assert [group.key for group in sort_groups(groups, "asc")] == ["", "CHEMISTRY", "HEMATOLOGY"]
    assert [group.key for group in sort_groups(groups, "desc")] == ["HEMATOLOGY", "CHEMISTRY", ""]


def test_aggregate_binding_resolver_handles_group_and_report_values() -> None:
    data = {
        "results": [
            {"amount": "10.5", "label": "A"},
            {"amount": "bad", "label": "B"},
            {"amount": 4.5, "label": "C"},
            {"label": "Missing"},
        ],
        "__slim_group__": {
            "key": "A",
            "field": "label",
            "rows": [
                {"amount": "10.5"},
                {"amount": "bad"},
                {"amount": 4.5},
            ],
        },
    }

    assert resolve_binding("group.count", data) == 3
    assert resolve_binding("group.sum.amount", data) == 15
    assert resolve_binding("group.avg.amount", data) == 7.5
    assert resolve_binding("group.min.amount", data) == 4.5
    assert resolve_binding("group.max.amount", data) == 10.5
    assert resolve_binding("report.count.results", data) == 4
    assert resolve_binding("report.sum.results.amount", data) == 15
    assert resolve_binding("report.avg.results.amount", data) == 7.5
    assert resolve_binding("report.sum.missing.amount", data) == ""


def test_system_binding_resolver_handles_page_and_datetime_values() -> None:
    data = {"__slim_page__": {"number": 2, "index": 1, "total_pages": 5, "count": 5}}

    assert resolve_binding("page.number", data) == 2
    assert resolve_binding("page.index", data) == 1
    assert resolve_binding("page.total_pages", data) == 5
    assert resolve_binding("page.count", data) == 5
    assert resolve_binding("date.today", data)
    assert resolve_binding("datetime.now", data)


def test_html_rendering_empty_repeating_detail_does_not_crash() -> None:
    report = repeating_report()

    html = render_html(report, {"results": []})

    assert "No results" in html


def test_pdf_rendering_expands_repeating_detail_rows() -> None:
    report = repeating_report()

    pdf = render_pdf(report, repeating_data())

    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000


def test_pdf_rendering_paginates_repeating_detail_rows() -> None:
    report = repeating_report()

    short_pdf = render_pdf(report, repeating_data())
    long_pdf = render_pdf(report, many_repeating_data())

    assert long_pdf.startswith(b"%PDF")
    assert len(long_pdf) > len(short_pdf)
    page_count = pdf_page_count(long_pdf)
    if page_count is not None:
        assert page_count > 1


def test_pdf_rendering_sets_export_metadata() -> None:
    report = load_report()
    report.page.print = {
        "pdf_title": "Custom PDF Title",
        "pdf_author": "QA Author",
        "pdf_subject": "Export Polish",
    }

    metadata = pdf_metadata(render_pdf(report, sample_data()))

    if metadata is None:
        pytest.skip("pypdf is not installed")
    assert metadata.title == "Custom PDF Title"
    assert metadata.author == "QA Author"
    assert metadata.subject == "Export Polish"


def test_html_rendering_basic_table_object() -> None:
    report = table_report()

    html = render_html(report, table_data())

    assert 'data-slim-object="results_table"' in html
    assert "<th" in html
    assert "Test" in html
    assert "Result" in html
    assert "WBC" in html
    assert "7.10" in html
    assert "background: #e5e7eb" in html


def test_html_rendering_paginates_basic_table_object() -> None:
    report = table_report()

    html = render_html(report, many_repeating_data())
    summary = pagination_summary(create_render_context(report), many_repeating_data())

    assert summary.page_count > 1
    assert summary.table_row_count == 36
    assert html.count('class="slim-report-page"') == summary.page_count
    assert html.count("<thead>") == summary.page_count
    assert "Nitrite" in html


def test_html_rendering_basic_table_missing_data_path_does_not_crash() -> None:
    report = table_report()

    html = render_html(report, {"results": "not an array"})

    assert 'data-slim-object="results_table"' in html
    assert "<!doctype html>" in html


def test_html_rendering_grouped_detail_rows() -> None:
    report = grouped_report()

    html = render_html(report, grouped_data())

    assert "HEMATOLOGY" in html
    assert "CHEMISTRY" in html
    assert "WBC" in html
    assert "FBS" in html
    assert "Count:" in html
    assert 'data-slim-object="group_count' in html
    assert 'data-slim-object="group_sum' in html
    assert 'data-slim-object="page_number' in html
    assert html.count('data-slim-object="group_name"') == 2
    assert html.count('data-slim-object="group_count"') == 2
    assert html.count('data-slim-object="group_sum"') == 2
    assert 'data-slim-object="group_name" style="left: 40.0px; top: 108.0px;' in html


def test_pdf_rendering_grouped_detail_rows() -> None:
    pdf = render_pdf(grouped_report(), grouped_data())

    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000


def test_pdf_rendering_basic_table_object() -> None:
    report = table_report()

    pdf = render_pdf(report, table_data())

    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000


def test_pdf_rendering_paginates_basic_table_object() -> None:
    report = table_report()

    short_pdf = render_pdf(report, table_data())
    long_pdf = render_pdf(report, many_repeating_data())

    assert long_pdf.startswith(b"%PDF")
    assert len(long_pdf) > len(short_pdf)
    page_count = pdf_page_count(long_pdf)
    if page_count is not None:
        assert page_count > 1


def test_pdf_rendering_basic_table_missing_data_path_does_not_crash() -> None:
    report = table_report()

    pdf = render_pdf(report, {})

    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000


def test_html_rendering_barcode_and_qrcode_objects() -> None:
    report = barcode_qr_report()

    html = render_html(report, {"order": {"id": "ORDER-42"}})

    assert 'data-slim-object="barcode_order_id"' in html
    assert 'data-slim-object="qr_order_id"' in html
    assert "ORDER-42" in html
    assert "repeating-linear-gradient" in html
    assert 'viewBox="0 0 29 29"' in html


def test_html_rendering_qrcode_content_is_square_and_centered() -> None:
    report = JSONSerializer().load_mapping(
        {
            "version": "1.0",
            "metadata": {"title": "Non-square QR"},
            "page": {"width": 300, "height": 200, "unit": "px"},
            "objects": [
                {
                    "id": "wide_qr",
                    "type": "qrcode",
                    "x": 10,
                    "y": 20,
                    "width": 140,
                    "height": 70,
                    "value": "ORDER-42",
                }
            ],
            "bands": [],
            "assets": [],
        }
    )

    html = render_html(report, {})

    assert 'data-slim-object="wide_qr"' in html
    assert "left: 35.0px; top: 0.0px;" in html
    assert "width: 70.0px; height: 70.0px;" in html
    assert "background-image: linear-gradient" not in html


def test_html_rendering_barcode_and_qrcode_value_fallbacks() -> None:
    report = barcode_qr_report()

    html = render_html(report, {})

    assert "1234567890" in html
    assert "https://example.com" in html


def test_pdf_rendering_barcode_and_qrcode_objects() -> None:
    report = barcode_qr_report()

    pdf = render_pdf(report, {"order": {"id": "ORDER-42"}})

    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000


def test_pdf_rendering_non_square_qrcode_object_does_not_crash() -> None:
    report = JSONSerializer().load_mapping(
        {
            "version": "1.0",
            "metadata": {"title": "Non-square QR PDF"},
            "page": {"width": 300, "height": 200, "unit": "px"},
            "objects": [
                {
                    "id": "wide_qr",
                    "type": "qrcode",
                    "x": 10,
                    "y": 20,
                    "width": 140,
                    "height": 70,
                    "value": "ORDER-42",
                }
            ],
            "bands": [],
            "assets": [],
        }
    )

    pdf = render_pdf(report, {})

    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000


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
    for template_name in (
        "cerebro_cbc",
        "lab_result",
        "repeating_lab_result",
        "grouped_lab_result",
        "aggregate_grouped_lab_result",
        "complete_sprint5_lab_report",
        "computed_fields_lab_result",
        "conditional_lab_result",
        "table_lab_result",
        "barcode_qr_lab_result",
    ):
        report = JSONSerializer().load(
            REPO_ROOT / f"examples/flask_app/sample_templates/{template_name}.json"
        )

        data = report.data.get("sample") if isinstance(report.data.get("sample"), dict) else sample_data()
        html = render_html(report, data)
        pdf = render_pdf(report, data)

        assert "<!doctype html>" in html
        assert "slim-report-page" in html
        assert len(html) > 1000
        assert pdf.startswith(b"%PDF")
        assert len(pdf) > 1000


def test_sample_templates_render_expected_content_with_embedded_data() -> None:
    cases = {
        "lab_result": ["LABORATORY RESULT", "250"],
        "cerebro_cbc": ["Cerebro CBC Result"],
        "repeating_lab_result": ["WBC", "HGB", "Nitrite"],
        "table_lab_result": ["Table Laboratory Result", "WBC", "Nitrite"],
        "grouped_lab_result": ["HEMATOLOGY", "CHEMISTRY", "URINALYSIS"],
        "aggregate_grouped_lab_result": [
            "HEMATOLOGY",
            "CHEMISTRY",
            "URINALYSIS",
            "Count: 2",
            "Total Tests:",
            "Page 1 of 1",
        ],
        "complete_sprint5_lab_report": [
            "COMPLETE LABORATORY RESULT",
            "JUAN DELA CRUZ",
            "Group Count:",
            "Total Results:",
        ],
        "computed_fields_lab_result": ["JUAN DELA CRUZ / 34 / Male", "HIGH"],
        "conditional_lab_result": ["Manual Review", "126 mg/dL"],
        "barcode_qr_lab_result": ["ORDER-1001", "repeating-linear-gradient"],
    }

    for template_name, expected_fragments in cases.items():
        report = JSONSerializer().load(
            REPO_ROOT / f"examples/flask_app/sample_templates/{template_name}.json"
        )
        data = report.data.get("sample") if isinstance(report.data.get("sample"), dict) else sample_data()

        html = render_html(report, data)

        assert "<!doctype html>" in html
        for fragment in expected_fragments:
            assert fragment in html, f"{template_name} missing {fragment!r}"
        assert 'data-slim-object="group_name__group__row_0"' not in html


def test_conditional_lab_result_sample_applies_rules_html_and_pdf() -> None:
    report = JSONSerializer().load(
        REPO_ROOT / "examples/flask_app/sample_templates/conditional_lab_result.json"
    )
    data = report.data["sample"]

    html = render_html(report, data)
    pdf = render_pdf(report, data)

    assert "126 mg/dL" in html
    assert "11.20 g/dL" in html
    assert "7.10 10^9/L" in html
    assert "color: #dc2626" in html
    assert "background: #fee2e2" in html
    assert "font-weight: 700" in html
    assert "color: #2563eb" in html
    assert "background: #dbeafe" in html
    assert "background: #fef3c7" in html
    assert "Manual Review" in html
    assert 'data-slim-object="row_result__group_chemistry_row_2"' not in html
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000


def test_computed_fields_sample_renders_formulas_html_and_pdf() -> None:
    report = JSONSerializer().load(
        REPO_ROOT / "examples/flask_app/sample_templates/computed_fields_lab_result.json"
    )
    data = report.data["sample"]

    html = render_html(report, data)
    pdf = render_pdf(report, data)

    assert "JUAN DELA CRUZ / 34 / Male" in html
    assert "7.10 10^9/L" in html
    assert "126.00" in html
    assert "HIGH" in html
    assert "Group Count: 3" in html
    assert "Page 1 of 1" in html
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


def repeating_data() -> dict:
    return {
        "results": [
            {"test": "WBC", "result": "7.10", "value": "7.1"},
            {"test": "HGB", "result": "14.20", "value": "13.2"},
        ]
    }


def many_repeating_data() -> dict:
    rows = [
        {"test": f"Test {index:02d}", "result": str(index), "value": str(index), "unit": "mg/dL"}
        for index in range(1, 36)
    ]
    rows.append({"test": "Nitrite", "result": "Negative", "value": "Negative", "unit": ""})
    return {"results": rows}


def repeating_report() -> Report:
    return JSONSerializer().load_mapping(
        {
            "version": "1.0",
            "metadata": {"title": "Repeating"},
            "page": {"width": 595, "height": 842, "unit": "px"},
            "objects": [
                {
                    "id": "title",
                    "type": "text",
                    "x": 40,
                    "y": 40,
                    "width": 200,
                    "height": 20,
                    "text": "LAB RESULT",
                    "band": "page_header",
                },
                {
                    "id": "row_test",
                    "type": "field",
                    "x": 40,
                    "y": 152,
                    "width": 100,
                    "height": 18,
                    "binding": "test",
                    "band": "detail",
                },
                {
                    "id": "row_value",
                    "type": "field",
                    "x": 160,
                    "y": 152,
                    "width": 100,
                    "height": 18,
                    "binding": "results[].value",
                    "band": "detail",
                },
                {
                    "id": "row_result",
                    "type": "field",
                    "x": 280,
                    "y": 152,
                    "width": 100,
                    "height": 18,
                    "binding": "result",
                    "band": "detail",
                },
                {
                    "id": "page_index",
                    "type": "field",
                    "x": 420,
                    "y": 800,
                    "width": 30,
                    "height": 18,
                    "binding": "page.index",
                    "band": "page_footer",
                },
                {
                    "id": "page_count",
                    "type": "field",
                    "x": 460,
                    "y": 800,
                    "width": 30,
                    "height": 18,
                    "binding": "page.count",
                    "band": "page_footer",
                },
            ],
            "bands": [
                {
                    "id": "page_header",
                    "type": "page_header",
                    "name": "Page Header",
                    "y": 0,
                    "height": 100,
                },
                {
                    "id": "detail",
                    "type": "detail",
                    "name": "Detail",
                    "y": 100,
                    "height": 680,
                    "repeat": {
                        "enabled": True,
                        "data_path": "results",
                        "row_height": 24,
                        "preview_rows": 10,
                        "empty_message": "No results",
                    },
                },
                {
                    "id": "page_footer",
                    "type": "page_footer",
                    "name": "Page Footer",
                    "y": 780,
                    "height": 62,
                },
            ],
            "assets": [],
        }
    )


def table_data() -> dict:
    return {
        "results": [
            {"test": "WBC", "result": "7.10", "unit": "10^9/L"},
            {"test": "HGB", "result": "14.20", "unit": "g/dL"},
        ]
    }


def table_report() -> Report:
    return JSONSerializer().load_mapping(
        {
            "version": "1.0",
            "metadata": {"title": "Table"},
            "page": {"width": 595, "height": 842, "unit": "px"},
            "objects": [
                {
                    "id": "results_table",
                    "type": "table",
                    "x": 40,
                    "y": 180,
                    "width": 300,
                    "height": 120,
                    "data_path": "results",
                    "header": {
                        "visible": True,
                        "height": 24,
                        "background_color": "#e5e7eb",
                        "color": "#111827",
                        "font_size": 10,
                        "bold": True,
                    },
                    "row": {
                        "height": 22,
                        "background_color": "#ffffff",
                        "alternate_background_color": "#f9fafb",
                        "color": "#111827",
                        "font_size": 10,
                    },
                    "border": {"width": 1, "color": "#d1d5db"},
                    "columns": [
                        {
                            "id": "test",
                            "label": "Test",
                            "binding": "test",
                            "width": 150,
                            "align": "left",
                        },
                        {
                            "id": "result",
                            "label": "Result",
                            "binding": "result",
                            "width": 90,
                            "align": "center",
                        },
                        {
                            "id": "unit",
                            "label": "Unit",
                            "binding": "unit",
                            "width": 80,
                            "align": "left",
                        },
                    ],
                }
            ],
            "bands": [],
            "assets": [],
        }
    )


def grouped_data() -> dict:
    return {
        "results": [
            {"section": "HEMATOLOGY", "test": "WBC", "value": "7.10"},
            {"section": "HEMATOLOGY", "test": "HGB", "value": "14.20"},
            {"section": "CHEMISTRY", "test": "FBS", "value": "95"},
        ]
    }


def grouped_report() -> Report:
    return JSONSerializer().load_mapping(
        {
            "version": "1.0",
            "metadata": {"title": "Grouped"},
            "page": {"width": 595, "height": 842, "unit": "px"},
            "objects": [
                {
                    "id": "group_name",
                    "type": "field",
                    "x": 40,
                    "y": 108,
                    "width": 180,
                    "height": 18,
                    "binding": "group.value",
                    "band": "group_header_results",
                },
                {
                    "id": "row_test",
                    "type": "field",
                    "x": 40,
                    "y": 140,
                    "width": 120,
                    "height": 18,
                    "binding": "test",
                    "band": "detail",
                },
                {
                    "id": "row_value",
                    "type": "field",
                    "x": 180,
                    "y": 140,
                    "width": 80,
                    "height": 18,
                    "binding": "value",
                    "band": "detail",
                },
                {
                    "id": "group_count_label",
                    "type": "text",
                    "x": 40,
                    "y": 758,
                    "width": 50,
                    "height": 18,
                    "text": "Count:",
                    "band": "group_footer_results",
                },
                {
                    "id": "group_count",
                    "type": "field",
                    "x": 90,
                    "y": 758,
                    "width": 50,
                    "height": 18,
                    "binding": "group.count",
                    "band": "group_footer_results",
                },
                {
                    "id": "group_sum",
                    "type": "field",
                    "x": 160,
                    "y": 758,
                    "width": 80,
                    "height": 18,
                    "binding": "group.sum.value",
                    "band": "group_footer_results",
                },
                {
                    "id": "page_number",
                    "type": "field",
                    "x": 430,
                    "y": 802,
                    "width": 40,
                    "height": 18,
                    "binding": "page.number",
                    "band": "page_footer",
                },
                {
                    "id": "page_total",
                    "type": "field",
                    "x": 480,
                    "y": 802,
                    "width": 40,
                    "height": 18,
                    "binding": "page.total_pages",
                    "band": "page_footer",
                },
            ],
            "bands": [
                {"id": "page_header", "type": "page_header", "y": 0, "height": 100},
                {
                    "id": "group_header_results",
                    "type": "group_header",
                    "y": 100,
                    "height": 28,
                    "group": {
                        "id": "results_section",
                        "data_path": "results",
                        "field": "section",
                        "sort": "none",
                    },
                },
                {
                    "id": "detail",
                    "type": "detail",
                    "y": 128,
                    "height": 628,
                    "repeat": {
                        "enabled": True,
                        "data_path": "results",
                        "row_height": 24,
                    },
                },
                {
                    "id": "group_footer_results",
                    "type": "group_footer",
                    "y": 756,
                    "height": 24,
                    "group": {"id": "results_section"},
                },
                {"id": "page_footer", "type": "page_footer", "y": 780, "height": 62},
            ],
            "assets": [],
        }
    )


def barcode_qr_report() -> Report:
    return JSONSerializer().load_mapping(
        {
            "version": "1.0",
            "metadata": {"title": "Barcode QR"},
            "page": {"width": 595, "height": 842, "unit": "px"},
            "objects": [
                {
                    "id": "barcode_order_id",
                    "type": "barcode",
                    "x": 40,
                    "y": 40,
                    "width": 160,
                    "height": 48,
                    "value": "1234567890",
                    "binding": "order.id",
                    "format": "code128",
                    "show_text": True,
                    "style": {
                        "foreground_color": "#111827",
                        "background_color": "#ffffff",
                        "font_size": 8,
                    },
                },
                {
                    "id": "qr_order_id",
                    "type": "qrcode",
                    "x": 220,
                    "y": 32,
                    "width": 80,
                    "height": 80,
                    "value": "https://example.com",
                    "binding": "order.id",
                    "error_correction": "M",
                    "style": {
                        "foreground_color": "#111827",
                        "background_color": "#ffffff",
                    },
                },
            ],
            "bands": [],
            "assets": [],
        }
    )


def pdf_page_count(pdf: bytes) -> int | None:
    try:
        from pypdf import PdfReader
    except ImportError:
        return None

    from io import BytesIO

    return len(PdfReader(BytesIO(pdf)).pages)


def pdf_metadata(pdf: bytes) -> object | None:
    try:
        from pypdf import PdfReader
    except ImportError:
        return None

    from io import BytesIO

    return PdfReader(BytesIO(pdf)).metadata
