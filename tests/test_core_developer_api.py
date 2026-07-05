from __future__ import annotations

from slim_report_core import (
    FieldObject,
    LineObject,
    ObjectFactory,
    RectangleObject,
    Report,
    TextObject,
)
from slim_report_core.serialization import JSONSerializer


def test_developer_api_builds_renders_and_round_trips_report() -> None:
    report = Report("Demo")
    page = report.page()

    page.text("Hello {{ patient.name }}", id="hello", x=50, y=40, font_size=18, bold=True)
    page.field("patient.name", id="patient_name", x=50, y=80)
    page.line(id="separator", x=50, y=110, width=500)
    page.rectangle(id="box", x=40, y=130, width=520, height=100)

    data = {"patient": {"name": "Juan Dela Cruz"}}
    html = report.render_html(data)
    pdf = report.render_pdf(data)

    assert report.validate().is_valid
    assert "Hello Juan Dela Cruz" in html
    assert "Juan Dela Cruz" in html
    assert pdf.startswith(b"%PDF")

    serializer = JSONSerializer()
    payload = serializer.dumps(report)
    loaded = serializer.loads(payload)

    assert serializer.dump_mapping(loaded) == serializer.dump_mapping(report)
    assert loaded.metadata.title == "Demo"
    assert isinstance(loaded.find("hello"), TextObject)
    assert isinstance(loaded.find("patient_name"), FieldObject)
    assert loaded.render_pdf(data).startswith(b"%PDF")


def test_page_convenience_methods_match_object_factory_shape() -> None:
    report = Report("Factory Match")
    page = report.page()
    factory = ObjectFactory()

    text = page.text("Hello", id="text", x=1, y=2, width=3, height=4, font_size=18)
    field = page.field("patient.name", id="field", x=5, y=6, width=7, height=8)
    line = page.line(id="line", x=9, y=10, width=11, height=0, stroke_width=2)
    rectangle = page.rectangle(id="rectangle", x=12, y=13, width=14, height=15, border_width=1)

    assert isinstance(text, TextObject)
    assert isinstance(field, FieldObject)
    assert isinstance(line, LineObject)
    assert isinstance(rectangle, RectangleObject)
    assert _without_page_id(text.to_dict()) == factory.create_text(
        "Hello",
        id="text",
        x=1,
        y=2,
        width=3,
        height=4,
        style_values={"font_size": 18},
    ).to_dict()
    assert _without_page_id(field.to_dict()) == factory.create_field(
        "patient.name",
        id="field",
        x=5,
        y=6,
        width=7,
        height=8,
    ).to_dict()
    assert _without_page_id(line.to_dict()) == factory.create_line(
        id="line",
        x=9,
        y=10,
        width=11,
        height=0,
        style_values={"stroke_width": 2},
    ).to_dict()
    assert _without_page_id(rectangle.to_dict()) == factory.create_rectangle(
        id="rectangle",
        x=12,
        y=13,
        width=14,
        height=15,
        style_values={"border_width": 1},
    ).to_dict()


def test_developer_api_defaults_to_valid_report_objects() -> None:
    report = Report("Valid Defaults")
    page = report.page()

    text = page.text("Hello")
    field = page.field("patient.name")
    line = page.line()
    rectangle = page.rectangle()

    assert [obj.id for obj in report.objects] == ["text_1", "field_1", "line_1", "rectangle_1"]
    assert all(obj.width >= 0 and obj.height >= 0 for obj in report.objects)
    assert text.text == "Hello"
    assert field.binding is not None
    assert field.binding.expression == "patient.name"
    assert line.type == "line"
    assert rectangle.type == "rectangle"
    assert report.validate().is_valid


def test_developer_api_keeps_invalid_input_explicit() -> None:
    report = Report("Invalid")
    page = report.page()

    page.field("")

    result = report.validate()

    assert not result.is_valid
    assert result.errors[0].code == "binding.required"


def _without_page_id(data: dict) -> dict:
    copied = dict(data)
    copied["properties"] = dict(copied.get("properties", {}))
    copied["properties"].pop("page_id", None)
    return copied
