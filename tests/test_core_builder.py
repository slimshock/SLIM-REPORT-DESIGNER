from __future__ import annotations

from slim_report_core import (
    Object,
    ObjectBuilder,
    Page,
    PageBuilder,
    Position,
    Report,
    ReportBuilder,
    Size,
    Style,
    StyleBuilder,
)


def test_report_builder_constructs_report_domain_model() -> None:
    builder = ReportBuilder("CBC Report")

    report = (
        builder.page("A4")
        .text("Complete Blood Count", x=50, y=40, font_size=18, bold=True)
        .field("patient.name", x=50, y=90)
        .line(x=50, y=120, width=500)
        .build()
    )

    assert isinstance(report, Report)
    assert report.metadata.title == "CBC Report"
    assert report.page.size == "a4"
    assert report.page.unit == "px"
    assert [report_object.type for report_object in report.objects] == ["text", "field", "line"]
    assert report.objects[0].text == "Complete Blood Count"
    assert report.objects[0].style.values["font_size"] == 18
    assert report.objects[0].style.values["bold"] is True
    assert report.objects[1].binding is not None
    assert report.objects[1].binding.expression == "patient.name"
    assert report.validate().is_valid


def test_report_builder_chains_across_page_breaks() -> None:
    report = (
        ReportBuilder("Invoice")
        .page("Letter")
        .text("Invoice", x=50, y=40)
        .field("customer.name", x=50, y=80)
        .rectangle(x=45, y=110, width=500, height=120)
        .line(x=45, y=250, width=500)
        .page_break()
        .page("Letter")
        .text("Terms", x=50, y=40)
        .build()
    )

    assert len(report.pages) == 2
    assert [page.size for page in report.pages] == ["letter", "letter"]
    assert [report_object.type for report_object in report.objects] == [
        "text",
        "field",
        "rectangle",
        "line",
        "text",
    ]
    assert report.objects[0].properties["page_id"] == report.pages[0].id
    assert report.objects[-1].properties["page_id"] == report.pages[1].id
    assert report.validate().is_valid


def test_report_builder_new_page_can_be_configured_explicitly() -> None:
    report = (
        ReportBuilder("Multi Page")
        .page("A4", id="cover")
        .text("Cover", x=10, y=10)
        .new_page("Letter", id="details", orientation="landscape")
        .text("Details", x=10, y=10)
        .build()
    )

    assert [page.id for page in report.pages] == ["cover", "details"]
    assert report.pages[1].orientation == "landscape"
    assert report.objects[0].properties["page_id"] == "cover"
    assert report.objects[1].properties["page_id"] == "details"


def test_report_builder_convenience_methods_reduce_boilerplate() -> None:
    report = (
        ReportBuilder()
        .metadata(
            title="Invoice",
            subtitle="July Billing",
            description="Monthly billing statement",
            author="Billing Team",
            category="finance",
        )
        .landscape()
        .margin(36)
        .header("ACME Billing")
        .title("Invoice")
        .subtitle("July Billing")
        .footer("Page {{ page }}")
        .build()
    )

    assert report.metadata.title == "Invoice"
    assert report.metadata.description == "Monthly billing statement"
    assert report.metadata.author == "Billing Team"
    assert report.metadata.custom["subtitle"] == "July Billing"
    assert report.metadata.custom["category"] == "finance"
    assert report.page.size == "letter"
    assert report.page.unit == "px"
    assert report.page.orientation == "landscape"
    assert report.page.margin.left == 36
    assert [report_object.properties["role"] for report_object in report.objects] == [
        "header",
        "title",
        "subtitle",
        "footer",
    ]
    assert report.find_by_name("title") is report.objects[1]
    assert report.objects[1].style.values["font_size"] == 20
    assert report.objects[1].style.values["bold"] is True
    assert report.objects[-1].y == 762
    assert report.validate().is_valid


def test_report_builder_portrait_and_page_builder_margin_aliases() -> None:
    report = ReportBuilder().landscape().portrait().margin(12, 24).build()
    page = PageBuilder().margin(8).build()

    assert report.page.orientation == "portrait"
    assert report.page.margin.top == 12
    assert report.page.margin.right == 24
    assert report.page.margin.bottom == 12
    assert report.page.margin.left == 24
    assert page.margin.top == 8
    assert page.margin.right == 8


def test_report_builder_adds_rectangle_and_named_style() -> None:
    report = (
        ReportBuilder("Styled Report")
        .style("heading", font_size=20, bold=True)
        .rectangle(x=10, y=20, width=200, height=80, border_width=1)
        .text("Heading", x=20, y=30, style={"font_size": 14})
        .build()
    )

    assert isinstance(report.styles["heading"], Style)
    assert report.styles["heading"].values == {"font_size": 20, "bold": True}
    assert report.objects[0].type == "rectangle"
    assert report.objects[0].style.values["border_width"] == 1
    assert report.objects[1].style.values["font_size"] == 14


def test_report_builder_generates_unique_object_ids() -> None:
    report = ReportBuilder().text("One").text("Two").field("patient.name").build()

    assert [report_object.id for report_object in report.objects] == [
        "text_1",
        "text_2",
        "field_1",
    ]


def test_report_builder_accepts_position_and_size_objects() -> None:
    report = (
        ReportBuilder("Geometry")
        .text("Title", position=Position(50, 40), size=Size(300, 30))
        .field("patient.name", position={"x": 50, "y": 90}, size={"width": 300, "height": 20})
        .rectangle(position=Position(45, 120), size=Size(500, 100))
        .build()
    )

    assert report.objects[0].position == Position(50, 40)
    assert report.objects[0].size == Size(300, 30)
    assert report.objects[1].x == 50
    assert report.objects[1].width == 300
    assert report.objects[2].position == Position(45, 120)
    assert report.objects[2].size == Size(500, 100)
    assert report.validate().is_valid


def test_page_builder_builds_page_domain_object() -> None:
    page = PageBuilder().size("Letter").landscape().margins(12, 24).build()

    assert isinstance(page, Page)
    assert page.size == "letter"
    assert page.orientation == "landscape"
    assert page.unit == "px"
    assert page.margin.top == 12
    assert page.margin.right == 24
    assert page.margin.bottom == 12
    assert page.margin.left == 24


def test_object_builder_builds_object_domain_object() -> None:
    report_object = (
        ObjectBuilder("field", object_id="patient_name", x=10, y=20, width=180, height=20)
        .binding("patient.name")
        .style(font_size=12, align="left")
        .name("Patient Name")
        .build()
    )

    assert isinstance(report_object, Object)
    assert report_object.id == "patient_name"
    assert report_object.binding is not None
    assert report_object.binding.expression == "patient.name"
    assert report_object.style.values["font_size"] == 12
    assert report_object.properties["name"] == "Patient Name"


def test_object_builder_accepts_position_and_size_objects() -> None:
    report_object = (
        ObjectBuilder(
            "rectangle",
            object_id="box",
            position=Position(10, 20),
            size=Size(200, 80),
        )
        .position(Position(15, 25))
        .size(width=220, height=90)
        .build()
    )

    assert report_object.position == Position(15, 25)
    assert report_object.size == Size(220, 90)


def test_object_builder_can_add_to_parent_report_builder() -> None:
    builder = ReportBuilder()

    builder.object("text", id="custom_title", x=10, y=10).text("Custom").add()
    report = builder.build()

    found = report.find("custom_title")
    assert found is not None
    assert found.text == "Custom"


def test_style_builder_builds_style_domain_object() -> None:
    style = StyleBuilder().font_size(16).bold().color("#111111").build()

    assert isinstance(style, Style)
    assert style.values == {"font_size": 16, "bold": True, "color": "#111111"}


def test_style_accepts_keyword_values_and_can_be_reused() -> None:
    title_style = Style(font_size=18, bold=True)

    report = (
        ReportBuilder("Laboratory")
        .text("Laboratory Report", x=50, y=40, style=title_style)
        .text("Final Result", x=50, y=80, style=title_style)
        .build()
    )

    assert title_style.values == {"font_size": 18, "bold": True}
    assert report.objects[0].style.to_dict() == {"font_size": 18, "bold": True}
    assert report.objects[1].style.to_dict() == {"font_size": 18, "bold": True}
    assert report.objects[0].style is title_style
    assert report.objects[1].style is title_style


def test_style_inheritance_resolves_parent_values() -> None:
    base_style = Style(font_family="Helvetica", font_size=12, color="#111111")
    title_style = base_style.inherit(font_size=18, bold=True)

    report = (
        ReportBuilder("Laboratory")
        .text("Laboratory Report", x=50, y=40, style=title_style)
        .build()
    )
    html = report.render_html({})

    assert title_style.values == {"font_size": 18, "bold": True}
    assert title_style.resolved_values() == {
        "font_family": "Helvetica",
        "font_size": 18,
        "color": "#111111",
        "bold": True,
    }
    assert report.objects[0].style.to_dict() == title_style.resolved_values()
    assert "font-size: 18.0px" in html
    assert "font-weight: 700" in html
    assert "color: #111111" in html


def test_style_from_dict_supports_parent_mapping() -> None:
    style = Style.from_dict(
        {
            "parent": {"font_family": "Helvetica", "font_size": 12},
            "font_size": 18,
            "bold": True,
        }
    )

    assert style.values == {"font_size": 18, "bold": True}
    assert style.resolved_values() == {
        "font_family": "Helvetica",
        "font_size": 18,
        "bold": True,
    }


def test_named_builder_styles_are_reusable_domain_styles() -> None:
    report = (
        ReportBuilder("Styled")
        .style("base", font_family="Helvetica", font_size=10)
        .build()
    )
    title_style = report.styles["base"].inherit(font_size=18, bold=True)

    child_report = ReportBuilder("Styled").text("Title", style=title_style).build()

    assert report.styles["base"].name == "base"
    assert title_style.resolved_values()["font_family"] == "Helvetica"
    assert title_style.resolved_values()["font_size"] == 18
    assert child_report.objects[0].style.resolved_values()["font_family"] == "Helvetica"
