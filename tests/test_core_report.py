from __future__ import annotations

import pytest

from slim_report_core import (
    DEFAULT_REPORT_VERSION,
    Asset,
    BarcodeObject,
    FieldObject,
    ImageObject,
    LineObject,
    Object,
    Page,
    Position,
    QRCodeObject,
    RectangleObject,
    Report,
    ReportObject,
    ReportObjectNotFoundError,
    ReportValidationError,
    Size,
    Style,
    TableObject,
    TextObject,
    create_default_template,
)
from slim_report_core.serialization import JSONSerializer


def test_create_default_template_has_required_empty_shape() -> None:
    template = create_default_template()

    assert template.to_dict() == {
        "version": DEFAULT_REPORT_VERSION,
        "metadata": {
            "title": "Untitled Report",
            "description": None,
            "author": None,
            "tags": [],
            "custom": {},
        },
        "page": {
            "width": 8.5,
            "height": 11.0,
            "unit": "in",
            "orientation": "portrait",
            "margin_top": 0.5,
            "margin_right": 0.5,
            "margin_bottom": 0.5,
            "margin_left": 0.5,
            "background_color": "#ffffff",
            "transparent": False,
        },
        "objects": [],
        "bands": [],
        "assets": [],
    }


def test_report_add_get_remove_object() -> None:
    report = Report()
    report_object = ReportObject(
        id="heading",
        type="text",
        width=4.0,
        height=0.5,
        properties={"text": "Monthly Sales"},
    )

    added = report.add_object(report_object)

    assert added is report_object
    assert report.get_object("heading") is report_object
    assert report.remove_object("heading") is report_object
    assert report.get_object("heading") is None


def test_report_rejects_duplicate_object_ids() -> None:
    report = Report()
    report.add_object({"id": "heading", "type": "text"})

    with pytest.raises(ReportValidationError):
        report.add_object({"id": "heading", "type": "text"})


def test_report_rejects_malformed_object() -> None:
    report = Report()

    with pytest.raises(ReportValidationError):
        report.add_object({"type": "text"})


def test_report_remove_missing_object_raises() -> None:
    report = Report()

    with pytest.raises(ReportObjectNotFoundError):
        report.remove_object("missing")


def test_report_exposes_domain_collections() -> None:
    report = Report()

    assert report.metadata.title == "Untitled Report"
    assert report.pages == [report.page]
    assert report.objects == []
    assert report.styles == {}
    assert report.assets == []


def test_report_convenience_accessors_are_callable() -> None:
    report = Report()

    metadata = report.metadata(title="Updated", subtitle="Draft", owner="Lab")
    heading = report.styles("heading", font_size=18, bold=True)
    report.assets.append(Asset(id="logo", type="image", source="logo.png"))

    assert metadata is report.metadata
    assert report.metadata().title == "Updated"
    assert report.metadata.custom["subtitle"] == "Draft"
    assert report.metadata.custom["owner"] == "Lab"
    assert report.pages() is report.pages
    assert report.styles() is report.styles
    assert report.styles["heading"] is heading
    assert report.assets() is report.assets
    assert report.assets()[0].id == "logo"


def test_report_constructor_accepts_title_for_primary_api() -> None:
    report = Report("Laboratory Report")

    assert report.metadata.title == "Laboratory Report"
    assert report.page() is report.page


def test_report_page_object_creation_api_matches_target_usage() -> None:
    report = Report("Laboratory Report")

    page = report.page()
    title = page.text("Laboratory Result", x=50, y=30)
    patient = page.field("patient.name", x=50, y=80)
    line = page.line(x=50, y=110, width=500)
    box = page.rectangle(x=40, y=140, width=520, height=120)

    assert [report_object.type for report_object in report.objects] == [
        "text",
        "field",
        "line",
        "rectangle",
    ]
    assert isinstance(title, TextObject)
    assert isinstance(patient, FieldObject)
    assert isinstance(line, LineObject)
    assert isinstance(box, RectangleObject)
    assert title.text == "Laboratory Result"
    assert patient.binding is not None
    assert patient.binding.expression == "patient.name"
    assert line.width == 500
    assert box.height == 120
    assert all(report_object.properties["page_id"] == page.id for report_object in report.objects)
    assert page.objects == list(report.objects)
    assert report.validate().is_valid


def test_page_placeholder_methods_create_report_objects() -> None:
    report = Report("Placeholders")
    page = report.page()

    image = page.image("logo.png", x=10, y=10, width=80, height=40)
    barcode = page.barcode("ABC123", x=10, y=60)
    qrcode = page.qrcode("https://example.test", x=10, y=130)
    table = page.table(binding="results", columns=[{"label": "Name", "field": "name"}])

    assert [report_object.type for report_object in report.objects] == [
        "image",
        "barcode",
        "qrcode",
        "table",
    ]
    assert isinstance(image, ImageObject)
    assert isinstance(barcode, BarcodeObject)
    assert isinstance(qrcode, QRCodeObject)
    assert isinstance(table, TableObject)
    assert image.properties["source"] == "logo.png"
    assert barcode.properties["value"] == "ABC123"
    assert barcode.properties["symbology"] == "code128"
    assert qrcode.properties["value"] == "https://example.test"
    assert table.properties["binding"] == "results"
    assert table.properties["columns"] == [{"label": "Name", "field": "name"}]
    assert all(report_object.properties["page_id"] == page.id for report_object in report.objects)
    assert report.validate().is_valid


def test_page_add_accepts_concrete_report_objects() -> None:
    report = Report("Manual")
    page = report.page()

    added = page.add(TextObject("Manual title", x=10, y=20))

    assert added in report.objects
    assert isinstance(added, TextObject)
    assert added.id == "text_1"
    assert added.properties["page_id"] == page.id


def test_page_behaves_like_object_collection() -> None:
    report = Report("Collection")
    page = report.page()
    title = page.text("Title", id="title")
    name = page.field("patient.name", id="patient_name")

    assert list(page) == [title, name]
    assert len(page) == 2
    assert page[0] is title
    assert title in page
    assert "patient_name" in page
    assert page.find("title") is title
    assert page.find("missing") is None


def test_page_remove_only_removes_objects_on_that_page() -> None:
    report = Report("Remove")
    first = report.page()
    second = report.new_page(id="details")
    title = first.text("Title", id="title")
    detail = second.text("Detail", id="detail")

    removed = first.remove("title")

    assert removed is title
    assert title not in report.objects
    assert second.objects == [detail]
    with pytest.raises(ReportObjectNotFoundError):
        first.remove("detail")


def test_page_clear_removes_page_objects() -> None:
    report = Report("Clear")
    first = report.page()
    second = report.new_page(id="details")
    first.text("Title", id="title")
    first.field("patient.name", id="patient")
    detail = second.text("Detail", id="detail")

    first.clear()

    assert first.objects == []
    assert report.objects == [detail]


def test_page_validate_returns_structured_result_for_page_scope() -> None:
    report = Report("Validate")
    page = report.page()
    page.field("", id="empty_binding")

    result = page.validate()

    assert not result.is_valid
    assert result.errors[0].code == "binding.required"


def test_page_objects_can_reuse_style_references() -> None:
    report = Report("Styled")
    page = report.page()
    title_style = Style(font_size=18, bold=True)

    title = page.text("Title", style=title_style)
    subtitle = page.text("Subtitle", style=title_style)
    title_style.values["color"] = "#111111"

    assert title.style is title_style
    assert subtitle.style is title_style
    assert title.style.resolved_values()["color"] == "#111111"
    assert subtitle.style.resolved_values()["color"] == "#111111"


def test_page_style_overrides_create_inherited_child_style() -> None:
    report = Report("Styled")
    page = report.page()
    body_style = Style(font_family="Helvetica", font_size=11)

    title = page.text("Title", style=body_style, font_size=18, bold=True)

    assert title.style is not body_style
    assert title.style.parent is body_style
    assert title.style.values == {"font_size": 18, "bold": True}
    assert title.style.resolved_values() == {
        "font_family": "Helvetica",
        "font_size": 18,
        "bold": True,
    }


def test_style_clone_preserves_values_without_sharing_references() -> None:
    base_style = Style(font_family="Helvetica", nested={"weight": "regular"})
    title_style = base_style.inherit(font_size=18, bold=True)

    cloned = title_style.clone()
    cloned.parent.values["nested"]["weight"] = "bold"
    cloned.values["font_size"] = 20

    assert title_style.resolved_values()["nested"]["weight"] == "regular"
    assert title_style.resolved_values()["font_size"] == 18
    assert cloned.resolved_values()["font_size"] == 20


def test_object_from_dict_dispatches_to_concrete_classes() -> None:
    objects = [
        Object.from_dict({"id": "title", "type": "text", "text": "Title"}),
        Object.from_dict({"id": "patient", "type": "field", "binding": "patient.name"}),
        Object.from_dict({"id": "line", "type": "line"}),
        Object.from_dict({"id": "box", "type": "rectangle"}),
        Object.from_dict({"id": "logo", "type": "image", "properties": {"source": "logo.png"}}),
        Object.from_dict({"id": "barcode", "type": "barcode", "properties": {"value": "123"}}),
        Object.from_dict({"id": "qr", "type": "qrcode", "properties": {"value": "123"}}),
        Object.from_dict({"id": "table", "type": "table", "properties": {"binding": "rows"}}),
    ]

    assert [type(report_object) for report_object in objects] == [
        TextObject,
        FieldObject,
        LineObject,
        RectangleObject,
        ImageObject,
        BarcodeObject,
        QRCodeObject,
        TableObject,
    ]


def test_concrete_report_object_clone_preserves_type() -> None:
    report_object = TextObject("Clone me", id="title", x=10, y=20)

    cloned = report_object.clone(new_ids=False)

    assert isinstance(cloned, TextObject)
    assert cloned.id == "title"
    assert cloned.text == "Clone me"


def test_report_new_page_returns_attached_page() -> None:
    report = Report("Multi Page")
    first_page = report.page()
    first_page.text("Cover")

    second_page = report.new_page("Letter", id="details")
    detail = second_page.text("Details")

    assert second_page in report.pages
    assert second_page.size == "letter"
    assert detail.properties["page_id"] == "details"
    assert first_page.objects[0].text == "Cover"
    assert second_page.objects == [detail]


def test_report_adds_and_removes_pages() -> None:
    report = Report()

    second_page = report.add_page(Page(id="details", width=816, height=1056, unit="px"))

    assert report.pages[1] is second_page
    assert report.remove_page("details") is second_page
    assert len(report.pages) == 1


def test_report_does_not_remove_last_page() -> None:
    report = Report()

    with pytest.raises(ReportValidationError):
        report.remove_page(0)


def test_report_find_object_aliases_get_object() -> None:
    report = Report()
    report_object = report.add_object(Object(id="title", type="text", text="Hello"))

    assert report.find_object("title") is report_object
    assert report.get_object("title") is report_object
    assert report.find_object("missing") is None


def test_object_supports_position_and_size_value_objects() -> None:
    report_object = Object(
        id="box",
        type="rectangle",
        position=Position(50, 40),
        size=Size(300, 40),
    )

    assert report_object.x == 50
    assert report_object.y == 40
    assert report_object.width == 300
    assert report_object.height == 40
    assert report_object.position == Position(50, 40)
    assert report_object.size == Size(300, 40)
    assert report_object.to_dict()["x"] == 50
    assert "position" not in report_object.to_dict()


def test_object_position_and_size_setters_update_legacy_coordinates() -> None:
    report_object = Object(id="box", type="rectangle")

    report_object.position = Position(25, 30)
    report_object.size = {"width": 120, "height": 60}

    assert report_object.x == 25
    assert report_object.y == 30
    assert report_object.width == 120
    assert report_object.height == 60


def test_object_from_dict_accepts_position_and_size_mappings() -> None:
    report_object = Object.from_dict(
        {
            "id": "box",
            "type": "rectangle",
            "position": {"x": 50, "y": 40},
            "size": {"width": 300, "height": 40},
        }
    )

    assert report_object.position == Position(50, 40)
    assert report_object.size == Size(300, 40)
    assert report_object.to_dict()["x"] == 50
    assert report_object.to_dict()["width"] == 300


def test_report_add_asset_and_reject_duplicate_asset_ids() -> None:
    report = Report()
    asset = report.add_asset(Asset(id="logo", type="image", source="logo.png"))

    assert report.assets == [asset]
    with pytest.raises(ReportValidationError):
        report.add_asset({"id": "logo", "type": "image", "source": "other.png"})


def test_report_clone_and_copy_are_deep_copies() -> None:
    report = Report(styles={"heading": Style({"font_size": 18})})
    report.metadata.title = "Original"
    report.add_object(Object(id="title", type="text", text="Original title"))

    cloned = report.clone(new_ids=False)
    copied = report.copy()
    cloned.metadata.title = "Clone"
    cloned.objects[0].text = "Changed"
    copied.styles["heading"].values["font_size"] = 20

    assert report.metadata.title == "Original"
    assert report.objects[0].text == "Original title"
    assert report.styles["heading"].values["font_size"] == 18


def test_json_serializer_loads_pages_layers_and_styles_into_report() -> None:
    payload = {
        "version": DEFAULT_REPORT_VERSION,
        "metadata": {"title": "Multi Page", "custom": {}},
        "page": {"width": 816, "height": 1056, "unit": "px", "orientation": "portrait"},
        "pages": [
            {"id": "cover", "width": 816, "height": 1056, "unit": "px"},
            {"id": "detail", "width": 816, "height": 1056, "unit": "px"},
        ],
        "objects": [{"id": "title", "type": "text", "text": "Hello"}],
        "bands": [],
        "layers": [{"id": "main", "name": "Main"}],
        "styles": {"heading": {"font_size": 18}},
        "assets": [],
    }

    serializer = JSONSerializer()
    report = serializer.load_mapping(payload)

    assert [page.id for page in report.pages] == ["cover", "detail"]
    assert report.layers[0].name == "Main"
    assert report.styles["heading"].values["font_size"] == 18
    assert serializer.dump_mapping(report)["pages"][1]["id"] == "detail"


def test_report_does_not_expose_json_persistence_methods() -> None:
    assert not hasattr(Report, "load_json")
    assert not hasattr(Report, "load_from_json")
    assert not hasattr(Report, "load_from_dict")
    assert not hasattr(Report(), "save_json")
    assert not hasattr(Report(), "to_json")
    assert not hasattr(Report(), "to_dict")
