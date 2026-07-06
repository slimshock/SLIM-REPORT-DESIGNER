from __future__ import annotations

import json
from pathlib import Path

from slim_report_core import DEFAULT_REPORT_VERSION, Band, Object, Page, Report, Style
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


def test_json_serializer_preserves_bands_and_object_band_alias() -> None:
    serializer = JSONSerializer()
    report = serializer.load_mapping(
        {
            "version": DEFAULT_REPORT_VERSION,
            "metadata": {"title": "Bands"},
            "page": {"width": 595, "height": 842, "unit": "px"},
            "objects": [
                {
                    "id": "header_title",
                    "type": "text",
                    "text": "Header",
                    "band": "page_header",
                }
            ],
            "bands": [
                {
                    "id": "page_header",
                    "type": "page_header",
                    "name": "Page Header",
                    "y": 0,
                    "height": 100,
                    "background_color": "#eeeeee",
                    "visible": True,
                    "locked": False,
                }
            ],
            "assets": [],
        }
    )

    dumped = serializer.dump_mapping(report)

    assert isinstance(report.bands[0], Band)
    assert report.bands[0].name == "Page Header"
    assert report.bands[0].y == 0
    assert report.bands[0].background_color == "#eeeeee"
    assert report.objects[0].band_id == "page_header"
    assert dumped["bands"][0]["background_color"] == "#eeeeee"
    assert dumped["objects"][0]["band"] == "page_header"


def test_json_serializer_round_trips_optional_data_metadata() -> None:
    payload = sample_template()
    payload["data"] = {
        "sample": {"patient": {"name": "Juan Dela Cruz"}},
        "fields": [{"path": "patient.name", "label": "Patient Name"}],
    }

    report = JSONSerializer().load_mapping(payload)
    dumped = JSONSerializer().dump_mapping(report)

    assert report.data["sample"]["patient"]["name"] == "Juan Dela Cruz"
    assert dumped["data"] == payload["data"]


def test_repeating_lab_result_sample_template_preserves_data_metadata(tmp_path: Path) -> None:
    sample_path = (
        Path(__file__).resolve().parents[1]
        / "examples/flask_app/sample_templates/repeating_lab_result.json"
    )
    payload = json.loads(sample_path.read_text(encoding="utf-8"))
    serializer = JSONSerializer()

    report = serializer.load_mapping(payload)
    saved_path = tmp_path / "repeating_lab_result.json"
    serializer.save(report, saved_path)
    loaded = serializer.load(saved_path)
    dumped = serializer.dump_mapping(loaded)

    assert loaded.data["sample"]["results"][0]["test"] == "WBC"
    assert loaded.data["sample"]["results"][1]["test"] == "RBC"
    assert loaded.data["fields"][0]["path"] == "laboratory.name"
    assert dumped["data"]["sample"] == payload["data"]["sample"]
    assert dumped["data"]["fields"] == payload["data"]["fields"]


def test_json_serializer_round_trips_basic_table_object() -> None:
    payload = sample_template()
    payload["objects"].append(
        {
            "id": "results_table",
            "type": "table",
            "x": 40,
            "y": 180,
            "width": 515,
            "height": 260,
            "data_path": "results",
            "header": {"visible": True, "height": 24},
            "row": {"height": 22},
            "border": {"width": 1, "color": "#d1d5db"},
            "columns": [
                {"id": "test", "label": "Test", "binding": "test", "width": 150},
                {"id": "result", "label": "Result", "binding": "result", "width": 90},
            ],
        }
    )

    report = JSONSerializer().load_mapping(payload)
    dumped = JSONSerializer().dump_mapping(report)
    table = next(item for item in dumped["objects"] if item["id"] == "results_table")

    assert table["type"] == "table"
    assert table["data_path"] == "results"
    assert table["columns"][0]["binding"] == "test"
    assert table["columns"][1]["label"] == "Result"
    assert table["header"]["height"] == 24
    assert table["border"]["color"] == "#d1d5db"


def test_json_serializer_round_trips_barcode_and_qrcode_objects() -> None:
    payload = sample_template()
    payload["objects"].extend([
        {
            "id": "barcode_order_id",
            "type": "barcode",
            "x": 40,
            "y": 160,
            "width": 160,
            "height": 48,
            "value": "1234567890",
            "binding": "order.id",
            "format": "code128",
            "show_text": True,
            "style": {
                "foreground_color": "#111827",
                "background_color": "#ffffff",
                "font_size": 8,
            },
        },
        {
            "id": "qr_order_id",
            "type": "qrcode",
            "x": 220,
            "y": 160,
            "width": 80,
            "height": 80,
            "value": "https://example.com",
            "binding": "order.id",
            "error_correction": "M",
            "style": {
                "foreground_color": "#111827",
                "background_color": "#ffffff",
            },
        },
    ])

    dumped = JSONSerializer().dump_mapping(JSONSerializer().load_mapping(payload))
    barcode = next(item for item in dumped["objects"] if item["id"] == "barcode_order_id")
    qrcode = next(item for item in dumped["objects"] if item["id"] == "qr_order_id")

    assert barcode["type"] == "barcode"
    assert barcode["binding"] == "order.id"
    assert barcode["value"] == "1234567890"
    assert barcode["format"] == "code128"
    assert barcode["show_text"] is True
    assert qrcode["type"] == "qrcode"
    assert qrcode["binding"] == "order.id"
    assert qrcode["error_correction"] == "M"


def test_json_serializer_omits_data_for_old_templates_without_data() -> None:
    dumped = JSONSerializer().dump_mapping(JSONSerializer().load_mapping(sample_template()))

    assert "data" not in dumped


def test_json_serializer_round_trips_detail_repeat_settings() -> None:
    payload = sample_template()
    payload["bands"] = [
        {
            "id": "detail",
            "type": "detail",
            "name": "Detail",
            "y": 100,
            "height": 500,
            "repeat": {
                "enabled": True,
                "data_path": "results",
                "row_height": 3,
                "preview_rows": 500,
                "empty_message": "No results",
            },
        }
    ]

    report = JSONSerializer().load_mapping(payload)
    dumped = JSONSerializer().dump_mapping(report)

    assert dumped["bands"][0]["repeat"] == {
        "enabled": True,
        "data_path": "results",
        "row_height": 8,
        "preview_rows": 100,
        "empty_message": "No results",
    }


def test_json_serializer_round_trips_page_pagination_settings() -> None:
    payload = sample_template()
    payload["page"]["pagination"] = {
        "enabled": True,
        "repeat_page_header": True,
        "repeat_page_footer": True,
        "respect_margins": True,
    }

    report = JSONSerializer().load_mapping(payload)
    dumped = JSONSerializer().dump_mapping(report)

    assert dumped["page"]["pagination"] == {
        "enabled": True,
        "repeat_page_header": True,
        "repeat_page_footer": True,
        "respect_margins": True,
    }


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
