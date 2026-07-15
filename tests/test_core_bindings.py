from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from slim_report_core import (
    Band,
    DatasetField,
    DatasetFieldBinding,
    MySQLConnectionConfig,
    Report,
    ReportBindingService,
    ReportDataset,
    ReportDataSource,
    ReportTemplate,
    ReportValidationError,
    TextObject,
)


def bound_report() -> Report:
    return Report(
        "Bindings",
        bands=[Band(id="detail", type="detail", y=100, height=200)],
        objects=[
            TextObject(
                "Patient name",
                id="patient_name",
                band_id="detail",
                x=20,
                y=120,
                width=180,
                height=24,
                properties={"custom": "preserved"},
            )
        ],
        data_sources=[
            ReportDataSource(
                id="main",
                name="Main",
                type="mysql",
                connection=MySQLConnectionConfig(
                    host="localhost", database="lis", username="report"
                ),
            )
        ],
        datasets=[
            ReportDataset(
                id="patients",
                name="Patients",
                data_source_id="main",
                source_type="view",
                view_name="report_patients",
                fields=[
                    DatasetField("patient_name", "string"),
                    DatasetField("birth_date", "date"),
                ],
            )
        ],
    )


def test_dataset_field_binding_is_immutable_and_canonical() -> None:
    binding = DatasetFieldBinding(" patients ", " patient_name ")

    assert binding.to_dict() == {
        "type": "datasetField",
        "datasetId": "patients",
        "field": "patient_name",
    }
    with pytest.raises(FrozenInstanceError):
        binding.field_name = "other"  # type: ignore[misc]
    with pytest.raises(ReportValidationError, match="datasetId"):
        DatasetFieldBinding(" ", "patient_name")
    with pytest.raises(ReportValidationError, match="field name"):
        DatasetFieldBinding("patients", " ")


def test_binding_and_band_context_round_trip_at_root_level() -> None:
    report = bound_report()
    ReportBindingService().bind_object(report, "patient_name", "patients", "patient_name")

    template = report.template.to_dict()
    object_json = template["objects"][0]
    band_json = template["bands"][0]
    assert object_json["dataBinding"] == {
        "type": "datasetField",
        "datasetId": "patients",
        "field": "patient_name",
    }
    assert "dataBinding" not in object_json["properties"]
    assert band_json["dataBinding"] == {"datasetId": "patients"}

    restored = Report(ReportTemplate.from_dict(template))
    assert restored.objects[0].dataset_binding == DatasetFieldBinding("patients", "patient_name")
    assert restored.bands[0].dataset_id == "patients"
    assert restored.clone().objects[0].dataset_binding == restored.objects[0].dataset_binding


def test_bind_validates_before_mutating_geometry_or_existing_content() -> None:
    report = bound_report()
    report.bands[0].dataset_id = "another_dataset"
    original = report.objects[0].to_dict()

    with pytest.raises(ReportValidationError, match="already bound"):
        ReportBindingService().bind_object(report, "patient_name", "patients", "patient_name")

    assert report.objects[0].to_dict() == original


def test_bind_and_clear_manage_band_context_without_destroying_text() -> None:
    report = bound_report()
    service = ReportBindingService()

    service.bind_object(report, "patient_name", "patients", "birth_date")
    report_object = report.objects[0]
    assert report_object.text == "{{patients.birth_date}}"
    assert (report_object.x, report_object.y, report_object.width, report_object.height) == (
        20,
        120,
        180,
        24,
    )
    assert report_object.properties["custom"] == "preserved"
    assert report.bands[0].dataset_id == "patients"

    service.clear_binding(report, "patient_name")
    assert report_object.dataset_binding is None
    assert report_object.text == "{{patients.birth_date}}"
    assert report.bands[0].dataset_id is None


def test_binding_service_get_and_find_helpers_use_exact_field_names() -> None:
    report = bound_report()
    service = ReportBindingService()
    changed = service.bind_object(report, "patient_name", "patients", "patient_name")

    assert changed is report.objects[0]
    assert service.get_binding(report, "patient_name") == DatasetFieldBinding(
        "patients", "patient_name"
    )
    assert service.find_dataset_bindings(report, "patients") == (report.objects[0],)
    assert service.find_field_bindings(report, "patients", "patient_name") == (report.objects[0],)
    assert service.find_field_bindings(report, "patients", "PATIENT_NAME") == ()


def test_validation_preserves_and_reports_broken_references() -> None:
    report = bound_report()
    report.objects[0].dataset_binding = DatasetFieldBinding("patients", "missing")
    report.bands[0].dataset_id = "patients"

    result = ReportBindingService().validate(report)

    assert not result.valid
    assert [issue.code for issue in result.issues] == ["missing_field"]
    assert report.objects[0].dataset_binding.field == "missing"


def test_invalid_structured_binding_is_rejected_during_deserialization() -> None:
    with pytest.raises(ReportValidationError, match="type"):
        TextObject.from_dict(
            {
                "id": "text_1",
                "type": "text",
                "text": "Broken",
                "dataBinding": {
                    "type": "expression",
                    "datasetId": "patients",
                    "field": "patient_name",
                },
            }
        )
