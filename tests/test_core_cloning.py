from __future__ import annotations

from slim_report_core import Asset, Band, Layer, Margin, Object, Page, Report, Style


def test_page_object_and_style_clone_are_deep_clones_with_new_ids_by_default() -> None:
    page = Page(id="page_main", margin=Margin(top=1))
    report_object = Object(
        id="patient_name",
        type="field",
        properties={"field": "patient.name", "nested": {"enabled": True}},
    )
    style = Style({"nested": {"font_size": 12}})

    cloned_page = page.clone()
    cloned_object = report_object.clone()
    cloned_style = style.clone()

    assert cloned_page.id != page.id
    assert cloned_page.margin is not page.margin
    assert cloned_object.id != report_object.id
    assert cloned_object.properties == report_object.properties
    assert cloned_object.properties is not report_object.properties
    assert cloned_style.values == style.values
    assert cloned_style.values is not style.values
    cloned_style.values["nested"]["font_size"] = 14
    assert style.values["nested"]["font_size"] == 12


def test_model_clone_can_preserve_ids() -> None:
    page = Page(id="page_main")
    report_object = Object(id="title", type="text")

    assert page.clone(new_ids=False).id == "page_main"
    assert report_object.clone(new_ids=False).id == "title"


def test_report_clone_generates_new_ids_and_remaps_references() -> None:
    report = Report(
        pages=[Page(id="page_main")],
        bands=[Band(id="detail", type="detail")],
        layers=[Layer(id="foreground", name="Foreground")],
        styles={"heading": Style({"font_size": 18})},
        assets=[Asset(id="logo", type="image", source="logo.png")],
    )
    report.add_object(
        Object(
            id="title",
            type="text",
            band_id="detail",
            layer_id="foreground",
            properties={"text": "Hello", "asset_id": "logo", "style_id": "heading"},
        )
    )

    cloned = report.clone()

    assert cloned.pages[0].id != "page_main"
    assert cloned.bands[0].id != "detail"
    assert cloned.layers[0].id != "foreground"
    assert cloned.objects[0].id != "title"
    assert cloned.assets[0].id != "logo"
    assert list(cloned.styles) != ["heading"]
    assert cloned.objects[0].band_id == cloned.bands[0].id
    assert cloned.objects[0].layer_id == cloned.layers[0].id
    assert cloned.objects[0].properties["asset_id"] == cloned.assets[0].id
    assert cloned.objects[0].properties["style_id"] == next(iter(cloned.styles))


def test_report_clone_can_preserve_ids() -> None:
    report = Report(
        pages=[Page(id="page_main")],
        assets=[Asset(id="logo", type="image", source="logo.png")],
    )
    report.add_object(Object(id="title", type="text"))

    cloned = report.clone(new_ids=False)

    assert cloned.pages[0].id == "page_main"
    assert cloned.objects[0].id == "title"
    assert cloned.assets[0].id == "logo"
    assert cloned.assets[0] is not report.assets[0]


def test_report_clone_can_share_asset_references() -> None:
    asset = Asset(id="logo", type="image", source="logo.png")
    report = Report(assets=[asset])

    cloned = report.clone(share_assets=True)

    assert cloned.assets == [asset]
    assert cloned.assets[0] is asset


def test_report_copy_preserves_ids_for_compatibility() -> None:
    report = Report(pages=[Page(id="page_main")])
    report.add_object(Object(id="title", type="text"))

    copied = report.copy()

    assert copied.pages[0].id == "page_main"
    assert copied.objects[0].id == "title"
    assert copied.objects[0] is not report.objects[0]
