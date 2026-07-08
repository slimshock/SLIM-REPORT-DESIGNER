from __future__ import annotations

from slim_report_core import Asset, Object, Page, Report, Style


def test_report_validate_returns_valid_result_for_default_report() -> None:
    result = Report().validate()

    assert result.is_valid
    assert result.errors == []
    assert result.to_dict() == {"valid": True, "errors": []}


def test_report_validate_returns_structured_errors_without_raising() -> None:
    report = Report()
    report.pages = []

    result = report.validate()

    assert not result.is_valid
    assert result.errors[0].to_dict() == {
        "code": "page.required",
        "path": "pages",
        "message": "Report must contain at least one page.",
        "severity": "error",
    }


def test_report_validate_checks_page_size_and_orientation() -> None:
    report = Report(pages=[Page(size="tabloid", orientation="diagonal", unit="parsec", width=0)])

    codes = {error.code for error in report.validate().errors}

    assert "page.size.unsupported" in codes
    assert "page.orientation.unsupported" in codes
    assert "page.unit.unsupported" in codes
    assert "page.width.invalid" in codes


def test_report_validate_checks_objects_unique_ids_and_bindings() -> None:
    report = Report()
    report.objects = [
        Object(id="patient", type="field"),
        Object(id="patient", type="unknown", width=-1),
        Object(id="title", type="text", text="{{ unsafe() }}"),
    ]

    errors = report.validate().errors
    codes = {error.code for error in errors}

    assert "binding.required" in codes
    assert "object.id.duplicate" in codes
    assert "object.type.unsupported" in codes
    assert "object.width.invalid" in codes
    assert "binding.expression.unsupported_function" in codes


def test_report_validate_accepts_repeating_array_bindings() -> None:
    report = Report()
    report.objects = [
        Object(id="row_test", type="field", binding="results[].test"),
        Object(id="row_value", type="field", binding="results[0].value"),
    ]

    errors = report.validate().errors

    assert [error for error in errors if error.path.endswith(".binding")] == []


def test_report_validate_checks_styles_and_assets() -> None:
    report = Report(styles={"heading": Style({"font_size": -1, "bold": "yes"})})
    report.assets = [
        Asset(id="logo", type="image", source="logo.png"),
        Asset(id="logo", type="", source=""),
    ]

    errors = report.validate().errors
    codes = {error.code for error in errors}

    assert "style.value.invalid" in codes
    assert "asset.id.duplicate" in codes
    assert "asset.type.required" in codes
    assert "asset.source.required" in codes
