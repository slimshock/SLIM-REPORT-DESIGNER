from __future__ import annotations

from slim_report_core.formula import evaluate_condition, evaluate_formula, evaluate_formula_result
from slim_report_core.models import Object
from slim_report_core.rendering.context import (
    RenderObject,
    object_with_conditional_style,
    resolve_binding,
)


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


def test_condition_evaluator_returns_boolean_and_rejects_invalid_syntax() -> None:
    data = {
        "flag": "H",
        "numeric_value": 12.4,
        "patient": {"sex": "F"},
        "__slim_group__": {"rows": [{"id": 1}, {"id": 2}, {"id": 3}, {"id": 4}, {"id": 5}]},
    }
    resolver = lambda identifier: resolve_binding(identifier, data)  # noqa: E731

    assert evaluate_condition("flag == 'H'", data, resolver=resolver) is True
    assert evaluate_condition("flag == 'L'", data, resolver=resolver) is False
    assert evaluate_condition("numeric_value > 10", data, resolver=resolver) is True
    assert evaluate_condition("patient.sex == 'F'", data, resolver=resolver) is True
    assert evaluate_condition("group.count > 3", data, resolver=resolver) is True
    assert evaluate_condition("group.count > 5", data, resolver=resolver) is False
    assert evaluate_condition("contains(flag, 'H')", data, resolver=resolver) is True
    assert evaluate_condition("concat(", data, resolver=resolver) is False
    assert (
        evaluate_condition("__import__('os').system('echo unsafe')", data, resolver=resolver)
        is False
    )


def test_conditional_styles_merge_in_order_and_hide() -> None:
    obj = RenderObject(
        id="result",
        type="field",
        x=0,
        y=0,
        width=100,
        height=20,
        binding="result",
        style={"color": "#111827", "bold": False},
        conditions=[
            {
                "id": "high",
                "enabled": True,
                "condition": "flag == 'H'",
                "style": {"color": "#dc2626", "bold": True},
            },
            {
                "id": "background",
                "enabled": True,
                "condition": "numeric_value > 10",
                "style": {"background_color": "#fee2e2"},
            },
        ],
    )

    styled = object_with_conditional_style(obj, {"flag": "H", "numeric_value": 12})
    assert styled is not None
    assert styled.style["color"] == "#dc2626"
    assert styled.style["bold"] is True
    assert styled.style["background_color"] == "#fee2e2"

    unchanged = object_with_conditional_style(obj, {"flag": "N", "numeric_value": 7})
    assert unchanged is obj

    hidden = RenderObject(
        id="hide",
        type="text",
        x=0,
        y=0,
        width=100,
        height=20,
        text="Hidden",
        conditions=[{"id": "hide", "enabled": True, "condition": "flag == 'H'", "action": "hide"}],
    )
    assert object_with_conditional_style(hidden, {"flag": "H"}) is None


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


def test_conditions_json_shape_round_trips() -> None:
    obj = Object.from_dict(
        {
            "id": "result",
            "type": "field",
            "binding": "result",
            "conditions": [
                {
                    "id": "high",
                    "enabled": True,
                    "condition": "flag == 'H'",
                    "action": "hide",
                    "style": {"color": "#dc2626", "bold": True},
                }
            ],
        }
    )

    serialized = obj.to_dict()

    assert serialized["conditions"][0]["id"] == "high"
    assert serialized["conditions"][0]["action"] == "hide"
    assert serialized["conditions"][0]["style"]["bold"] is True
    assert serialized["properties"]["conditions"][0]["condition"] == "flag == 'H'"
