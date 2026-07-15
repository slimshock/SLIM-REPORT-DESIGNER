from __future__ import annotations

import json

import pytest

from slim_report_core import (
    DatasetField,
    InvalidNewReportConfigurationError,
    InvalidNewReportLayoutError,
    MySQLConnectionConfig,
    NewReportConfiguration,
    NewReportDataConfiguration,
    NewReportFieldSelectionError,
    NewReportLayoutConfiguration,
    NewReportPageConfiguration,
    NewReportWizardBuilder,
    QueryParameter,
    ReportBindingService,
    ReportDataset,
    ReportDataSource,
    SelectedReportField,
    calculate_column_widths,
    friendly_field_label,
)


def mysql_data() -> NewReportDataConfiguration:
    source = ReportDataSource(
        id="main_mysql",
        name="Main MySQL",
        type="mysql",
        connection=MySQLConnectionConfig(
            host="db.internal",
            database="lis",
            username="report_user",
            password="runtime-secret",
            password_ref="MYSQL_PASSWORD",
        ),
    )
    dataset = ReportDataset(
        id="patient_results",
        name="Patient Results",
        data_source_id=source.id,
        source_type="query",
        query="SELECT patient_id, patient_name, result_value FROM report_results "
        "WHERE released_at >= :date_from",
        parameters=[QueryParameter("date_from", "date", required=True)],
        fields=[
            DatasetField("patient_id", "integer", nullable=False),
            DatasetField("patient_name", "string", nullable=False),
            DatasetField("result_value", "decimal"),
            DatasetField("released_at", "datetime"),
        ],
    )
    return NewReportDataConfiguration(source, dataset)


def tabular_configuration(**layout_overrides: object) -> NewReportConfiguration:
    layout_values = {
        "layout_type": "tabular",
        "selected_fields": (
            SelectedReportField("patient_id", "Patient ID", 1),
            SelectedReportField("patient_name", "Patient Name", 2),
            SelectedReportField("result_value", "Result Value", 3),
        ),
        **layout_overrides,
    }
    return NewReportConfiguration(
        "Laboratory Results",
        description="Result listing",
        page=NewReportPageConfiguration(size="A4", orientation="landscape"),
        data=mysql_data(),
        layout=NewReportLayoutConfiguration(**layout_values),
    )


def test_blank_report_builds_metadata_page_and_default_bands() -> None:
    report = NewReportWizardBuilder().build(
        NewReportConfiguration(
            " Blank Report ",
            description=" Optional description ",
            page=NewReportPageConfiguration(size="Letter", orientation="portrait"),
        )
    )

    assert report.metadata.title == "Blank Report"
    assert report.metadata.description == "Optional description"
    assert (report.page.width, report.page.height) == (612, 792)
    assert [band.id for band in report.bands] == ["page_header", "detail", "page_footer"]
    assert not report.data_sources
    assert not report.datasets
    assert not report.objects
    assert report.validate().is_valid
    json.dumps(report.template.to_dict())


def test_mysql_blank_layout_preserves_metadata_without_objects_or_context() -> None:
    report = NewReportWizardBuilder().build(
        NewReportConfiguration(
            "Configured Blank",
            data=mysql_data(),
            layout=NewReportLayoutConfiguration(layout_type="blank"),
        )
    )

    assert [source.id for source in report.data_sources] == ["main_mysql"]
    assert [dataset.id for dataset in report.datasets] == ["patient_results"]
    assert len(report.datasets[0].fields) == 4
    assert len(report.datasets[0].parameters) == 1
    assert not report.objects
    assert all(band.dataset_id is None for band in report.bands)
    payload = json.dumps(report.template.to_dict())
    assert "runtime-secret" not in payload
    assert "temporary" not in payload


def test_tabular_layout_generates_aligned_headers_and_bound_details() -> None:
    report = NewReportWizardBuilder().build(tabular_configuration())
    headers = [item for item in report.objects if item.id.startswith("header_")]
    details = [item for item in report.objects if item.id.startswith("field_")]

    assert report.find_object("report_title").text == "Laboratory Results"
    assert [item.text for item in headers] == ["Patient ID", "Patient Name", "Result Value"]
    assert [item.dataset_binding.field_name for item in details] == [
        "patient_id",
        "patient_name",
        "result_value",
    ]
    assert [item.x for item in headers] == [item.x for item in details]
    assert [item.width for item in headers] == pytest.approx([item.width for item in details])
    assert sum(item.width for item in details) == pytest.approx(
        report.page.width - report.page.margin.left - report.page.margin.right
    )
    assert details[0].style.get("align") == "right"
    assert details[1].style.get("align") == "left"
    detail_band = next(band for band in report.bands if band.id == "detail")
    assert detail_band.dataset_id == "patient_results"
    assert all(detail_band.y <= item.y < detail_band.y + detail_band.height for item in details)
    assert ReportBindingService().validate(report).valid
    assert len({item.id for item in report.objects}) == len(report.objects)


@pytest.mark.parametrize(
    ("size", "orientation", "expected"),
    [
        ("A4", "portrait", (595, 842)),
        ("A4", "landscape", (842, 595)),
        ("Letter", "portrait", (612, 792)),
        ("Legal", "landscape", (1008, 612)),
    ],
)
def test_standard_page_sizes(size: str, orientation: str, expected: tuple[int, int]) -> None:
    report = NewReportWizardBuilder().build(
        NewReportConfiguration(
            "Page",
            page=NewReportPageConfiguration(size=size, orientation=orientation),
        )
    )
    assert (report.page.width, report.page.height) == expected


def test_custom_page_and_invalid_margins() -> None:
    report = NewReportWizardBuilder().build(
        NewReportConfiguration(
            "Custom",
            page=NewReportPageConfiguration(size="Custom", width=720, height=420),
        )
    )
    assert (report.page.width, report.page.height) == (420, 720)

    with pytest.raises(InvalidNewReportConfigurationError, match="printable"):
        NewReportWizardBuilder().build(
            NewReportConfiguration(
                "Invalid",
                page=NewReportPageConfiguration(
                    size="Custom",
                    width=100,
                    height=100,
                    margin_left=50,
                    margin_right=50,
                ),
            )
        )


def test_field_selection_rejects_missing_duplicate_and_empty_tabular_fields() -> None:
    with pytest.raises(NewReportFieldSelectionError, match="at least one"):
        NewReportWizardBuilder().build(tabular_configuration(selected_fields=()))
    with pytest.raises(NewReportFieldSelectionError, match="does not exist"):
        NewReportWizardBuilder().build(
            tabular_configuration(selected_fields=(SelectedReportField("missing", order=1),))
        )
    with pytest.raises(NewReportFieldSelectionError, match="more than once"):
        NewReportWizardBuilder().build(
            tabular_configuration(
                selected_fields=(
                    SelectedReportField("patient_id", order=1),
                    SelectedReportField("patient_id", order=2),
                )
            )
        )


def test_layout_requires_matching_mysql_data_relationship() -> None:
    data = mysql_data()
    data.dataset.data_source_id = "other"
    with pytest.raises(InvalidNewReportConfigurationError, match="does not reference"):
        NewReportWizardBuilder().build(NewReportConfiguration("Bad", data=data))


def test_column_widths_are_deterministic_bounded_and_warn_when_narrow() -> None:
    fields = tuple(mysql_data().dataset.fields[:3])
    first = calculate_column_widths(500, fields)
    second = calculate_column_widths(500, fields)
    assert first == second
    assert sum(first) == pytest.approx(500)
    assert all(width >= 48 for width in first)

    many = tuple(DatasetField(f"field_{index}") for index in range(20))
    with pytest.raises(InvalidNewReportLayoutError, match="readable"):
        calculate_column_widths(500, many)
    widths = calculate_column_widths(500, many, allow_narrow=True)
    assert sum(widths) == pytest.approx(500)
    assert all(width > 0 for width in widths)


def test_friendly_labels_preserve_common_acronyms() -> None:
    assert friendly_field_label("patient_id") == "Patient ID"
    assert friendly_field_label("wbc_result") == "WBC Result"
    assert friendly_field_label("released_at") == "Released At"
