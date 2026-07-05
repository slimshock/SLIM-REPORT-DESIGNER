from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

import pytest

from slim_report_core import (
    DataContext,
    DataProviderRegistry,
    ReportValidationError,
    resolve_expression,
    resolve_text,
)


@dataclass
class Patient:
    name: str


def test_resolve_expression_supports_nested_dictionaries() -> None:
    data = {
        "patient": {"name": "Maria Santos"},
        "order": {"id": "ORD-1001"},
        "result": {"HGB": 13.7},
    }

    assert resolve_expression("{{ patient.name }}", data) == "Maria Santos"
    assert resolve_expression("order.id", data) == "ORD-1001"
    assert resolve_expression("{{ result.HGB }}", data) == 13.7


def test_resolve_expression_supports_array_path_segments() -> None:
    data = {
        "results": [
            {"test": "WBC", "value": "7.1"},
            {"test": "HGB", "value": "13.2"},
        ]
    }

    assert resolve_expression("results[0].test", data) == "WBC"
    assert resolve_expression("results[].value", data) == "7.1"
    assert resolve_expression("results[1].value", data) == "13.2"


def test_resolve_expression_supports_object_attributes() -> None:
    data = {"patient": Patient(name="Juan Dela Cruz")}

    assert resolve_expression("{{ patient.name }}", data) == "Juan Dela Cruz"


def test_resolve_expression_uses_context_for_page_values() -> None:
    context = {"page": 2, "pages": 8}

    assert resolve_expression("{{ page }}", {}, context=context) == 2
    assert resolve_expression("{{ pages }}", {}, context=context) == 8


def test_resolve_expression_missing_values_return_empty_string() -> None:
    assert resolve_expression("{{ patient.middle_name }}", {"patient": {"name": "Ana"}}) == ""
    assert resolve_expression("{{ missing }}", {}) == ""


def test_resolve_expression_supports_limited_safe_functions() -> None:
    today = resolve_expression("{{ today() }}", {})
    now = resolve_expression("{{ now() }}", {})

    assert today == date.today().isoformat()
    assert datetime.fromisoformat(now)


def test_resolve_expression_does_not_evaluate_arbitrary_code() -> None:
    expression = "{{ __import__('os').system('echo unsafe') }}"

    assert resolve_expression(expression, {}) == ""


def test_resolve_text_replaces_multiple_expressions() -> None:
    data = {"patient": {"name": "Lina"}, "result": {"HGB": 12.9}}
    context = {"page": 1, "pages": 3}

    resolved = resolve_text(
        "Patient: {{ patient.name }} | HGB: {{ result.HGB }} | Page {{ page }}/{{ pages }}",
        data,
        context=context,
    )

    assert resolved == "Patient: Lina | HGB: 12.9 | Page 1/3"


def test_data_context_resolves_expressions_and_text() -> None:
    data_context = DataContext(
        data={"patient": {"name": "Ramon"}},
        context={"page": 4, "pages": 10},
    )

    assert data_context.resolve_expression("{{ patient.name }}") == "Ramon"
    assert data_context.resolve_text("Page {{ page }} of {{ pages }}") == "Page 4 of 10"


def test_data_provider_registry_registers_and_resolves_providers() -> None:
    registry = DataProviderRegistry()

    registry.register("patient", lambda patient_id: {"id": patient_id, "name": "Eva"})

    assert registry.list() == ["patient"]
    assert registry.get("patient") is not None
    assert registry.resolve("patient", "P-001") == {"id": "P-001", "name": "Eva"}


def test_data_provider_registry_validates_provider_registration() -> None:
    registry = DataProviderRegistry()

    with pytest.raises(ReportValidationError):
        registry.register("", lambda: None)

    with pytest.raises(ReportValidationError):
        registry.register("patient", "not callable")  # type: ignore[arg-type]

    with pytest.raises(ReportValidationError):
        registry.resolve("missing")
