from __future__ import annotations

from slim_report_core.formula import evaluate_formula, evaluate_formula_result
from slim_report_core.models import Object
from slim_report_core.rendering.context import resolve_binding


def test_formula_functions_and_math() -> None:
    assert evaluate_formula("concat('A', 'B')") == "AB"
    assert evaluate_formula("upper('abc')") == "ABC"
    assert evaluate_formula("lower('ABC')") == "abc"
    assert evaluate_formula("trim(' A ')") == "A"
    assert evaluate_formula("number(1.234, 2)") == "1.23"
    assert evaluate_formula("default('', 'N/A')") == "N/A"
    assert evaluate_formula("if(true, 'Y', 'N')") == "Y"
    assert evaluate_formula("numeric_value * 2", {"numeric_value": 7}) == 14


def test_formula_resolves_data_row_group_and_page_context() -> None:
    data = {
        "patient": {"name": "Juan"},
        "__slim_group__": {
            "field": "section",
            "key": "CHEMISTRY",
            "rows": [{"value": "1.5"}, {"value": "2.5"}],
        },
        "__slim_page__": {"number": 2, "total_pages": 4},
    }
    row = {"result": "7.10", "unit": "10^9/L", "flag": "H", "numeric_value": 7.1}
    resolver = lambda identifier: resolve_binding(  # noqa: E731
        identifier,
        data,
        row=row,
        repeat_data_path="results",
    )

    assert evaluate_formula("patient.name", data, resolver=resolver) == "Juan"
    assert evaluate_formula("concat(result, ' ', unit)", data, resolver=resolver) == "7.10 10^9/L"
    assert evaluate_formula("if(flag == 'H', 'HIGH', 'NORMAL')", data, resolver=resolver) == "HIGH"
    assert evaluate_formula("group.count", data, resolver=resolver) == 2
    assert evaluate_formula("page.number", data, resolver=resolver) == 2


def test_invalid_and_unsafe_formulas_do_not_execute() -> None:
    assert not evaluate_formula_result("concat(").ok
    assert not evaluate_formula_result("__import__('os').system('echo unsafe')").ok
    assert not evaluate_formula_result("[1, 2, 3]").ok


def test_formula_field_json_shape_round_trips() -> None:
    field = Object.from_dict(
        {
            "id": "computed_result",
            "type": "field",
            "binding": "",
            "formula": "concat(result, ' ', unit)",
            "formula_mode": True,
        }
    )

    serialized = field.to_dict()

    assert serialized["binding"] == ""
    assert serialized["formula"] == "concat(result, ' ', unit)"
    assert serialized["formula_mode"] is True
    assert serialized["properties"]["formula"] == "concat(result, ' ', unit)"
