from __future__ import annotations

import json
from datetime import date, datetime, time
from decimal import Decimal

import pytest

from slim_report_core import (
    DatasetSourceType,
    DatasetValidationError,
    QueryParameter,
    Report,
    ReportDataset,
    ReportDataSource,
    ReportRuntimeParameterService,
    RuntimeParameterConversionError,
    RuntimeParameterDatasetError,
    RuntimeParameterDefinitionError,
    RuntimeParameterMissingError,
    RuntimeParameterResolutionPolicy,
    RuntimeParameterResolver,
    RuntimeParameterUnknownError,
)


def query_dataset(
    *parameters: QueryParameter,
    dataset_id: str = "orders",
    name: str = "Daily Orders",
) -> ReportDataset:
    return ReportDataset(
        id=dataset_id,
        name=name,
        data_source_id="mysql",
        source_type="query",
        query="SELECT order_id FROM report_orders WHERE client_id = :client_id",
        parameters=list(parameters),
    )


def report_with(*datasets: ReportDataset) -> Report:
    return Report(
        data_sources=[
            ReportDataSource(
                id="mysql",
                name="Reporting",
                type="mysql",
                connection={
                    "host": "localhost",
                    "database": "reports",
                    "username": "reader",
                },
            )
        ],
        datasets=list(datasets),
    )


def test_schema_preserves_order_labels_and_safe_defaults() -> None:
    dataset = query_dataset(
        QueryParameter("date_from", "date", required=True, default=date(2026, 1, 1)),
        QueryParameter("client_id", "integer", label="Client ID", default=0),
        QueryParameter("released", "boolean", default=False),
    )

    schema = RuntimeParameterResolver().schema_for_dataset(dataset)

    assert [item.name for item in schema.parameters] == ["date_from", "client_id", "released"]
    assert schema.parameters[0].label == "Date From"
    assert schema.parameters[1].label == "Client ID"
    assert schema.to_dict()["parameters"] == [
        {
            "name": "date_from",
            "dataType": "date",
            "required": True,
            "label": "Date From",
            "hasDefault": True,
            "default": "2026-01-01",
        },
        {
            "name": "client_id",
            "dataType": "integer",
            "required": False,
            "label": "Client ID",
            "hasDefault": True,
            "default": 0,
        },
        {
            "name": "released",
            "dataType": "boolean",
            "required": False,
            "label": "Released",
            "hasDefault": True,
            "default": False,
        },
    ]


def test_view_schema_is_empty_and_view_resolution_is_rejected() -> None:
    dataset = ReportDataset(
        id="view",
        name="Approved View",
        data_source_id="mysql",
        source_type=DatasetSourceType.VIEW,
        view_name="report_orders",
    )
    resolver = RuntimeParameterResolver()

    assert resolver.schema_for_dataset(dataset).parameters == ()
    with pytest.raises(RuntimeParameterDatasetError, match="query-based"):
        resolver.resolve_dataset(dataset)


def test_resolution_precedence_and_tracking_preserves_zero_and_false() -> None:
    dataset = query_dataset(
        QueryParameter("client_id", "integer", required=True, default=12),
        QueryParameter("released", "boolean", required=True, default=True),
        QueryParameter("limit", "integer", default=50),
    )

    resolved = RuntimeParameterResolver().resolve_dataset(
        dataset,
        {"client_id": 0, "released": False},
        application_values={"client_id": 99},
    )

    assert dict(resolved.values) == {"client_id": 0, "released": False, "limit": 50}
    assert resolved.provided_parameters == ("client_id", "released")
    assert resolved.used_defaults == ("limit",)
    with pytest.raises(TypeError):
        resolved.values["client_id"] = 5  # type: ignore[index]


def test_missing_null_and_blank_rules() -> None:
    resolver = RuntimeParameterResolver()
    required = query_dataset(QueryParameter("client_id", "integer", required=True))
    optional = query_dataset(QueryParameter("client_id", "integer"))
    optional_string = query_dataset(QueryParameter("search", "string"))

    with pytest.raises(RuntimeParameterMissingError):
        resolver.resolve_dataset(required)
    with pytest.raises(RuntimeParameterMissingError):
        resolver.resolve_dataset(required, {"client_id": None})
    assert resolver.resolve_dataset(optional, {"client_id": None}).values["client_id"] is None
    assert resolver.resolve_dataset(optional, {"client_id": "  "}).values["client_id"] is None
    assert resolver.resolve_dataset(optional_string, {"search": ""}).values["search"] is None


@pytest.mark.parametrize(
    ("data_type", "raw", "expected"),
    [
        ("string", "  value  ", "  value  "),
        ("integer", "-10", -10),
        ("float", "-0.25", -0.25),
        ("decimal", "-5.750", Decimal("-5.750")),
        ("boolean", "YES", True),
        ("boolean", 0, False),
        ("date", "2026-01-31", date(2026, 1, 31)),
        ("time", "08:30:15", time(8, 30, 15)),
        ("datetime", "2026-01-31T08:30", datetime(2026, 1, 31, 8, 30)),
    ],
)
def test_supported_type_conversion(data_type: str, raw: object, expected: object) -> None:
    dataset = query_dataset(QueryParameter("value", data_type, required=True))
    resolved = RuntimeParameterResolver().resolve_dataset(dataset, {"value": raw})
    assert resolved.values["value"] == expected


@pytest.mark.parametrize(
    ("data_type", "raw", "code"),
    [
        ("integer", True, "invalid_integer"),
        ("integer", "1.5", "invalid_integer"),
        ("float", "NaN", "non_finite_float"),
        ("float", "Infinity", "non_finite_float"),
        ("decimal", "NaN", "non_finite_decimal"),
        ("boolean", "on", "invalid_boolean"),
        ("boolean", 2, "invalid_boolean"),
        ("date", "2026-02-30", "invalid_date"),
        ("time", "25:00", "invalid_time"),
        ("datetime", "not-a-date", "invalid_datetime"),
    ],
)
def test_invalid_values_have_safe_codes(data_type: str, raw: object, code: str) -> None:
    dataset = query_dataset(QueryParameter("value", data_type, required=True, label="Safe Label"))

    with pytest.raises(RuntimeParameterConversionError) as raised:
        RuntimeParameterResolver().resolve_dataset(dataset, {"value": raw})

    assert raised.value.code == code
    assert str(raw) not in str(raised.value)


def test_string_limit_and_policy_validation() -> None:
    resolver = RuntimeParameterResolver(
        policy=RuntimeParameterResolutionPolicy(max_string_length=3)
    )
    dataset = query_dataset(QueryParameter("search", "string", required=True))

    with pytest.raises(RuntimeParameterConversionError) as raised:
        resolver.resolve_dataset(dataset, {"search": "four"})
    assert raised.value.code == "string_too_long"
    with pytest.raises(ValueError):
        RuntimeParameterResolutionPolicy(max_parameters=0)


def test_unknown_names_are_case_sensitive_and_can_be_ignored_by_policy() -> None:
    dataset = query_dataset(QueryParameter("client_id", "integer"))

    with pytest.raises(RuntimeParameterUnknownError) as raised:
        RuntimeParameterResolver().resolve_dataset(dataset, {"CLIENT_ID": 12})
    assert "12" not in str(raised.value)

    resolver = RuntimeParameterResolver(
        policy=RuntimeParameterResolutionPolicy(reject_unknown_values=False)
    )
    assert resolver.resolve_dataset(dataset, {"extra": "secret"}).values["client_id"] is None


def test_invalid_configured_default_is_reported_as_definition_error() -> None:
    dataset = query_dataset(QueryParameter("client_id", "integer", default="not-an-integer"))

    with pytest.raises(RuntimeParameterDefinitionError) as raised:
        RuntimeParameterResolver().schema_for_dataset(dataset)

    assert "not-an-integer" not in str(raised.value)


def test_parameter_defaults_are_json_safe_and_reload_through_converter() -> None:
    parameters = [
        QueryParameter("amount", "decimal", default=Decimal("10.250")),
        QueryParameter("day", "date", default=date(2026, 1, 31)),
        QueryParameter("at", "time", default=time(8, 30, 15)),
        QueryParameter("stamp", "datetime", default=datetime(2026, 1, 31, 8, 30)),
    ]
    payload = query_dataset(*parameters).to_dict()
    reloaded = ReportDataset.from_dict(json.loads(json.dumps(payload)))
    resolved = RuntimeParameterResolver().resolve_dataset(reloaded)

    assert resolved.values["amount"] == Decimal("10.250")
    assert resolved.values["day"] == date(2026, 1, 31)
    assert resolved.values["at"] == time(8, 30, 15)
    assert resolved.values["stamp"] == datetime(2026, 1, 31, 8, 30)
    with pytest.raises(DatasetValidationError, match="supported scalar"):
        QueryParameter("bad", default={"secret": "value"})


def test_report_resolution_is_ordered_isolated_and_non_mutating() -> None:
    first = query_dataset(
        QueryParameter("client_id", "integer", required=True),
        dataset_id="first",
        name="First",
    )
    second = query_dataset(
        QueryParameter("client_id", "string", required=True),
        dataset_id="second",
        name="Second",
    )
    report = report_with(first, second)
    values = {"second": {"client_id": "B"}, "first": {"client_id": 7}}

    resolved = ReportRuntimeParameterService().resolve_report(
        report,
        values,
        dataset_ids=("second", "first"),
    )

    assert [item.dataset_id for item in resolved] == ["second", "first"]
    assert resolved[0].values["client_id"] == "B"
    assert resolved[1].values["client_id"] == 7
    assert values == {"second": {"client_id": "B"}, "first": {"client_id": 7}}
    assert report.datasets[0].parameters[0].default is None


def test_report_service_rejects_missing_dataset_and_primary_ambiguity() -> None:
    report = report_with(
        query_dataset(dataset_id="first", name="First"),
        query_dataset(dataset_id="second", name="Second"),
    )
    service = ReportRuntimeParameterService()

    with pytest.raises(RuntimeParameterDatasetError, match="missing"):
        service.schema_for_report(report, ("missing",))
    with pytest.raises(RuntimeParameterDatasetError, match="Select the dataset"):
        service.schema_for_primary_dataset(report)


def test_validation_result_never_exposes_submitted_value() -> None:
    dataset = query_dataset(QueryParameter("client_id", "integer", required=True))
    result = RuntimeParameterResolver().validate_dataset(dataset, {"client_id": "private"})

    assert not result.valid
    assert result.issues[0].parameter_name == "client_id"
    assert "private" not in result.issues[0].message
