from __future__ import annotations

from pathlib import Path

from slim_report_core import DEFAULT_REPORT_VERSION, Object, Page, Report, Style
from slim_report_core.serialization import JSONSerializer


def test_json_serializer_loads_mapping_into_report_domain_model() -> None:
    serializer = JSONSerializer()

    report = serializer.load_mapping(sample_template())

    assert isinstance(report, Report)
    assert report.metadata.title == "Serializer Test"
    assert report.page.size == "letter"
    assert report.objects[0].binding.expression == "patient.name"


def test_json_serializer_dumps_report_to_json_compatible_mapping() -> None:
    report = Report()
    report.metadata.title = "Domain Report"
    report.add_object(Object(id="title", type="text", text="Hello"))

    dumped = JSONSerializer().dump_mapping(report)

    assert dumped["metadata"]["title"] == "Domain Report"
    assert dumped["objects"][0]["text"] == "Hello"
    assert dumped["objects"][0]["properties"]["text"] == "Hello"


def test_json_serializer_round_trips_payload_string() -> None:
    serializer = JSONSerializer()
    report = serializer.load_mapping(sample_template())

    payload = serializer.dumps(report)
    loaded = serializer.loads(payload)

    assert serializer.dump_mapping(loaded) == serializer.dump_mapping(report)


def test_json_serializer_loads_and_saves_file(tmp_path: Path) -> None:
    serializer = JSONSerializer()
    report = Report()
    report.metadata.title = "File Report"
    report.add_object(Object(id="field", type="field", properties={"field": "patient.name"}))
    path = tmp_path / "template.json"

    serializer.save(report, path)
    loaded = serializer.load(path)

    assert loaded.metadata.title == "File Report"
    assert loaded.objects[0].binding.expression == "patient.name"


def test_json_serializer_preserves_domain_collections() -> None:
    report = Report(
        pages=[
            Page(id="cover", width=816, height=1056, unit="px"),
            Page(id="details", width=816, height=1056, unit="px"),
        ],
        styles={"heading": Style({"font_size": 18})},
    )

    dumped = JSONSerializer().dump_mapping(report)
    loaded = JSONSerializer().load_mapping(dumped)

    assert [page.id for page in loaded.pages] == ["cover", "details"]
    assert loaded.styles["heading"].values["font_size"] == 18


def test_json_serializer_serializes_resolved_style_values() -> None:
    base_style = Style(font_family="Helvetica", font_size=11)
    title_style = base_style.inherit(font_size=18, bold=True)
    report = Report(styles={"title": title_style})
    report.page().text("Title", id="title", style=title_style)

    dumped = JSONSerializer().dump_mapping(report)
    loaded = JSONSerializer().load_mapping(dumped)

    assert dumped["styles"]["title"] == {
        "font_family": "Helvetica",
        "font_size": 18,
        "bold": True,
    }
    assert dumped["objects"][0]["style"] == dumped["styles"]["title"]
    assert loaded.styles["title"].resolved_values()["font_family"] == "Helvetica"
    assert loaded.objects[0].style.resolved_values()["font_size"] == 18


def sample_template() -> dict:
    return {
        "version": DEFAULT_REPORT_VERSION,
        "metadata": {
            "title": "Serializer Test",
            "description": None,
            "author": None,
            "tags": [],
            "custom": {},
        },
        "page": {
            "size": "letter",
            "orientation": "portrait",
            "unit": "px",
        },
        "objects": [
            {
                "id": "patient_name",
                "type": "field",
                "x": 50,
                "y": 90,
                "width": 300,
                "height": 20,
                "binding": "patient.name",
            },
        ],
        "bands": [],
        "assets": [],
    }
