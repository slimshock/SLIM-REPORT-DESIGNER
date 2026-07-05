from __future__ import annotations

from slim_report_core import Object, Report, ReportObjectCollection


def test_report_objects_collection_is_list_like_and_callable() -> None:
    report = Report()
    title = report.add_object(Object(id="title", type="text", properties={"name": "Title"}))
    field = report.add_object(Object(id="patient_name", type="field"))

    assert isinstance(report.objects, ReportObjectCollection)
    assert report.objects == [title, field]
    assert report.objects() == [title, field]
    assert report.objects(lambda obj: obj.type == "field") == [field]


def test_report_find_supports_ids_and_predicates() -> None:
    report = Report()
    title = report.add_object(Object(id="title", type="text"))
    field = report.add_object(Object(id="patient_name", type="field"))

    assert report.find("title") is title
    assert report.find(lambda obj: obj.type == "field") is field
    assert report.find("missing") is None


def test_report_find_by_name_uses_object_name_property() -> None:
    report = Report()
    title = report.add_object(Object(id="title", type="text", properties={"name": "Header"}))

    assert report.find_by_name("Header") is title
    assert report.find_by_name("Missing") is None


def test_report_type_queries_support_predicates() -> None:
    report = Report()
    primary_text = report.add_object(
        Object(id="primary_title", type="text", properties={"role": "primary"})
    )
    report.add_object(Object(id="secondary_title", type="text", properties={"role": "secondary"}))
    field = report.add_object(Object(id="patient_name", type="field"))
    image = report.add_object(Object(id="logo", type="image"))
    table = report.add_object(Object(id="results", type="table"))

    assert report.text_objects(lambda obj: obj.properties.get("role") == "primary") == [
        primary_text
    ]
    assert report.fields() == [field]
    assert report.images() == [image]
    assert report.tables() == [table]


def test_report_objects_assignment_wraps_plain_lists() -> None:
    report = Report()

    report.objects = [Object(id="title", type="text")]

    assert isinstance(report.objects, ReportObjectCollection)
    assert report.objects(lambda obj: obj.type == "text") == report.objects
