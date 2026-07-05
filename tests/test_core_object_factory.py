from __future__ import annotations

import slim_report_core.models as model_module
from slim_report_core import (
    DEFAULT_REPORT_VERSION,
    FieldObject,
    LineObject,
    ObjectFactory,
    Page,
    RectangleObject,
    Report,
    Style,
    TextObject,
)
from slim_report_core.serialization import JSONSerializer


def test_object_factory_creates_supported_objects() -> None:
    factory = ObjectFactory()
    title_style = Style(font_size=18, bold=True)

    text = factory.create_text("Title", id="title", style=title_style)
    field = factory.create_field("patient.name", id="patient")
    line = factory.create_line(id="separator")
    rectangle = factory.create_rectangle(id="box")

    assert isinstance(text, TextObject)
    assert isinstance(field, FieldObject)
    assert isinstance(line, LineObject)
    assert isinstance(rectangle, RectangleObject)
    assert text.style is title_style
    assert field.binding is not None
    assert field.binding.expression == "patient.name"


def test_object_factory_style_overrides_create_inherited_style() -> None:
    factory = ObjectFactory()
    body_style = Style(font_family="Helvetica", font_size=11)

    text = factory.create_text(
        "Title",
        style=body_style,
        style_values={"font_size": 18, "bold": True},
    )

    assert text.style.parent is body_style
    assert text.style.resolved_values() == {
        "font_family": "Helvetica",
        "font_size": 18,
        "bold": True,
    }


def test_object_factory_creates_concrete_objects_from_mapping() -> None:
    factory = ObjectFactory()

    text = factory.create_from_dict(
        {
            "id": "title",
            "type": "text",
            "text": "Title",
            "style": {"font_size": 18},
        }
    )

    assert isinstance(text, TextObject)
    assert text.text == "Title"
    assert text.style.values["font_size"] == 18


def test_page_helpers_use_object_factory(monkeypatch) -> None:
    class RecordingFactory(ObjectFactory):
        def __init__(self) -> None:
            self.created_text = False

        def create_text(self, *args, **kwargs):
            self.created_text = True
            return super().create_text(*args, **kwargs)

    factory = RecordingFactory()
    monkeypatch.setattr(model_module, "_object_factory", lambda: factory)

    page = Report("Factory").page()
    created = page.text("Title")

    assert factory.created_text
    assert isinstance(created, TextObject)


def test_json_serializer_uses_object_factory() -> None:
    class RecordingFactory(ObjectFactory):
        def __init__(self) -> None:
            self.created_ids: list[str] = []

        def create_from_dict(self, data, *, object_class=None):
            self.created_ids.append(str(data["id"]))
            return super().create_from_dict(data, object_class=object_class)

    factory = RecordingFactory()
    report = JSONSerializer(object_factory=factory).load_mapping(
        {
            "version": DEFAULT_REPORT_VERSION,
            "metadata": {},
            "page": Page().to_dict(),
            "objects": [
                {"id": "title", "type": "text", "text": "Title"},
                {"id": "patient", "type": "field", "binding": "patient.name"},
            ],
            "bands": [],
            "assets": [],
        }
    )

    assert factory.created_ids == ["title", "patient"]
    assert isinstance(report.objects[0], TextObject)
    assert isinstance(report.objects[1], FieldObject)
