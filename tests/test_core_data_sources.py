from __future__ import annotations

import pytest

from slim_report_core import (
    DatasetField,
    DatasetSourceType,
    DatasetValidationError,
    DataSourceValidationError,
    EnvironmentCredentialResolver,
    MySQLConnectionConfig,
    QueryParameter,
    Report,
    ReportDataset,
    ReportDataSource,
)
from slim_report_core.serialization import JSONSerializer


def mysql_config(**overrides: object) -> MySQLConnectionConfig:
    values = {
        "host": "localhost",
        "port": 3306,
        "database": "lis",
        "username": "report_user",
        "password_ref": "SLIM_REPORT_MYSQL_PASSWORD",
    }
    values.update(overrides)
    return MySQLConnectionConfig(**values)


def data_source(**overrides: object) -> ReportDataSource:
    values = {
        "id": "main_mysql",
        "name": "Main MySQL",
        "type": "mysql",
        "connection": mysql_config(),
    }
    values.update(overrides)
    return ReportDataSource(**values)


def dataset(**overrides: object) -> ReportDataset:
    values = {
        "id": "patient_results",
        "name": "Patient Results",
        "data_source_id": "main_mysql",
        "source_type": DatasetSourceType.VIEW,
        "view_name": "report_patient_results",
    }
    values.update(overrides)
    return ReportDataset(**values)


def minimal_template() -> dict:
    return {
        "version": "1.0",
        "metadata": {"title": "Old Report"},
        "page": {"width": 8.5, "height": 11, "unit": "in"},
        "objects": [],
        "bands": [],
        "assets": [],
    }


def test_valid_mysql_configuration_serializes_password_reference() -> None:
    config = mysql_config()

    assert config.to_dict() == {
        "type": "mysql",
        "host": "localhost",
        "port": 3306,
        "database": "lis",
        "username": "report_user",
        "passwordRef": "SLIM_REPORT_MYSQL_PASSWORD",
        "charset": "utf8mb4",
        "connectTimeout": 10,
        "queryTimeout": 30,
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("host", ""),
        ("port", 0),
        ("port", 65536),
        ("database", ""),
        ("username", ""),
    ],
)
def test_mysql_configuration_rejects_invalid_required_values(
    field: str,
    value: object,
) -> None:
    with pytest.raises(DataSourceValidationError):
        mysql_config(**{field: value})


def test_plain_text_password_is_excluded_from_normal_serialization() -> None:
    config = mysql_config(password="secret", password_ref=None)

    assert "password" not in config.to_dict()
    assert config.to_dict(include_password=True)["password"] == "secret"


def test_environment_credential_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLIM_REPORT_MYSQL_PASSWORD", "resolved-secret")

    config = mysql_config(password=None)

    assert config.resolve_password(EnvironmentCredentialResolver()) == "resolved-secret"


def test_data_source_serialization_round_trip() -> None:
    source = data_source()

    loaded = ReportDataSource.from_dict(source.to_dict())

    assert loaded == source


def test_data_source_rejects_unsupported_type() -> None:
    with pytest.raises(DataSourceValidationError):
        data_source(type="postgres")


def test_view_dataset_validation_and_serialization() -> None:
    report_dataset = dataset(view_name="lis.report_patient_results")

    dumped = report_dataset.to_dict()
    loaded = ReportDataset.from_dict(dumped)

    assert dumped["sourceType"] == "view"
    assert dumped["viewName"] == "lis.report_patient_results"
    assert "query" not in dumped
    assert loaded.view_name == "lis.report_patient_results"


@pytest.mark.parametrize("view_name", ["bad view", "view;drop", "view--comment", "db.view.more"])
def test_view_dataset_rejects_invalid_view_names(view_name: str) -> None:
    with pytest.raises(DatasetValidationError):
        dataset(view_name=view_name)


def test_query_dataset_validation_preserves_query_formatting() -> None:
    query = "\nSELECT *\nFROM report_patient_results\nWHERE patient_id = :patient_id\n"

    report_dataset = dataset(
        source_type=DatasetSourceType.QUERY,
        view_name="ignored",
        query=query,
        parameters=[QueryParameter("patient_id", data_type="integer", required=True)],
    )

    assert report_dataset.view_name is None
    assert report_dataset.query == query
    assert report_dataset.to_dict()["query"] == query


def test_query_dataset_rejects_empty_query() -> None:
    with pytest.raises(DatasetValidationError):
        dataset(source_type=DatasetSourceType.QUERY, query="   ")


def test_dataset_rejects_unsupported_source_type() -> None:
    with pytest.raises(DatasetValidationError):
        dataset(source_type="table")


def test_field_serialization_round_trip_and_unknown_type() -> None:
    field = DatasetField(
        name="result_value",
        data_type="varchar2",
        nullable=False,
        label="Result",
        source_name="Result Value",
    )

    loaded = DatasetField.from_dict(field.to_dict())

    assert field.data_type == "unknown"
    assert loaded == field


def test_parameter_name_validation_and_serialization_round_trip() -> None:
    parameter = QueryParameter(
        "patient_id",
        data_type="integer",
        required=True,
        default=1001,
        label="Patient",
    )

    assert QueryParameter.from_dict(parameter.to_dict()) == parameter
    with pytest.raises(DatasetValidationError):
        QueryParameter("patient-id")


def test_dataset_rejects_duplicate_field_names() -> None:
    with pytest.raises(DatasetValidationError):
        dataset(
            fields=[
                DatasetField("Result"),
                DatasetField("result"),
            ]
        )


def test_dataset_rejects_duplicate_parameter_names() -> None:
    with pytest.raises(DatasetValidationError):
        dataset(
            source_type=DatasetSourceType.QUERY,
            query="SELECT * FROM report_patient_results WHERE id = :id",
            parameters=[
                QueryParameter("PatientId"),
                QueryParameter("patientid"),
            ],
        )


def test_report_rejects_duplicate_data_source_ids() -> None:
    report = Report()
    report.add_data_source(data_source())

    with pytest.raises(DataSourceValidationError):
        report.add_data_source(data_source(name="Other"))


def test_report_rejects_duplicate_dataset_ids_and_names() -> None:
    report = Report()
    report.add_data_source(data_source())
    report.add_dataset(dataset())

    with pytest.raises(DatasetValidationError):
        report.add_dataset(dataset(name="Other"))
    with pytest.raises(DatasetValidationError):
        report.add_dataset(dataset(id="other", name="patient results"))


def test_report_rejects_dataset_referencing_missing_data_source() -> None:
    report = Report()

    with pytest.raises(DatasetValidationError):
        report.add_dataset(dataset())


def test_report_prevents_removing_in_use_data_source_without_cascade() -> None:
    report = Report()
    source = report.add_data_source(data_source())
    report_dataset = report.add_dataset(dataset())

    with pytest.raises(DataSourceValidationError):
        report.remove_data_source(source.id)

    assert report.remove_data_source(source.id, cascade=True) is source
    assert report.get_dataset(report_dataset.id) is None


def test_old_report_without_data_sources_loads_with_empty_collections() -> None:
    report = JSONSerializer().load_mapping(minimal_template())

    assert report.data_sources == []
    assert report.datasets == []


def test_data_bound_report_saves_and_reopens_without_password(tmp_path) -> None:
    report = Report("Data Bound")
    report.add_data_source(data_source(connection=mysql_config(password="secret")))
    report.add_dataset(dataset(fields=[DatasetField("patient_name", source_name="patient_name")]))
    path = tmp_path / "report.json"

    serializer = JSONSerializer()
    serializer.save(report, path)
    loaded = serializer.load(path)
    dumped = serializer.dump_mapping(loaded)

    assert loaded.get_data_source("main_mysql") is not None
    assert loaded.get_dataset("patient_results") is not None
    assert "password" not in dumped["dataSources"][0]["connection"]
    assert dumped["dataSources"][0]["connection"]["passwordRef"] == ("SLIM_REPORT_MYSQL_PASSWORD")


def test_unknown_future_json_properties_do_not_crash_loading() -> None:
    payload = minimal_template()
    payload["dataSources"] = [
        {
            "id": "main_mysql",
            "name": "Main MySQL",
            "type": "mysql",
            "connection": mysql_config().to_dict(),
            "futureProperty": {"ignored": True},
        }
    ]
    payload["datasets"] = [
        {
            "id": "patient_results",
            "name": "Patient Results",
            "dataSourceId": "main_mysql",
            "sourceType": "view",
            "viewName": "report_patient_results",
            "futureProperty": "ignored",
        }
    ]

    report = JSONSerializer().load_mapping(payload)

    assert report.get_data_source("main_mysql") is not None
    assert report.get_dataset("patient_results") is not None
