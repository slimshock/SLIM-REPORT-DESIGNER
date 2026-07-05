from __future__ import annotations

from slim_report_core import HTMLExporter, Object, Page, Report, ReportEvent, render_html


def test_report_event_listener_receives_domain_event() -> None:
    report = Report()
    events: list[ReportEvent] = []

    report.on("object_added", events.append)
    added = report.add_object(Object(id="title", type="text"))

    assert [event.name for event in events] == ["object_added"]
    assert events[0].source is report
    assert events[0].payload["object"] is added


def test_report_event_listener_can_be_removed() -> None:
    report = Report()
    events: list[ReportEvent] = []

    report.on("object_added", events.append)
    report.off("object_added", events.append)
    report.add_object(Object(id="title", type="text"))

    assert events == []


def test_object_and_page_mutation_events_are_emitted() -> None:
    report = Report()
    events: list[tuple[str, str]] = []

    def listener(event: ReportEvent) -> None:
        item = event.payload.get("object") or event.payload.get("page")
        events.append((event.name, item.id))

    for event_name in ("object_added", "object_removed", "page_added", "page_removed"):
        report.on(event_name, listener)

    report.add_object(Object(id="title", type="text"))
    report.remove_object("title")
    report.add_page(Page(id="details"))
    report.remove_page("details")

    assert events == [
        ("object_added", "title"),
        ("object_removed", "title"),
        ("page_added", "details"),
        ("page_removed", "details"),
    ]


def test_render_events_are_emitted_for_report_render_methods() -> None:
    report = Report()
    report.add_object(Object(id="title", type="text", text="Hello"))
    events: list[str] = []

    report.on("before_render", lambda event: events.append(event.name))
    report.on("after_render", lambda event: events.append(event.name))

    html = report.render_html({})

    assert "Hello" in html
    assert events == ["before_render", "after_render"]


def test_public_render_api_emits_report_render_events() -> None:
    report = Report()
    report.add_object(Object(id="title", type="text", text="Hello"))
    events: list[str] = []
    report.on("before_render", lambda event: events.append(event.name))

    render_html(report, {})

    assert events == ["before_render"]


def test_report_render_emits_export_and_render_events_in_order() -> None:
    report = Report()
    report.add_object(Object(id="title", type="text", text="Hello"))
    events: list[str] = []

    for event_name in ("before_export", "before_render", "after_render", "after_export"):
        report.on(event_name, lambda event: events.append(event.name))

    report.render({}, exporter="html")

    assert events == ["before_export", "before_render", "after_render", "after_export"]


def test_direct_exporter_emits_export_events() -> None:
    report = Report()
    report.add_object(Object(id="title", type="text", text="Hello"))
    events: list[str] = []

    report.on("before_export", lambda event: events.append(event.name))
    report.on("after_export", lambda event: events.append(event.name))

    HTMLExporter().export(report)

    assert events == ["before_export", "after_export"]
