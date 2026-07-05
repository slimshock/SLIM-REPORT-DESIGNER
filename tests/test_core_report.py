from __future__ import annotations

import json

import pytest

from slim_report_core import (
    DEFAULT_REPORT_VERSION,
    Report,
    ReportObject,
    ReportObjectNotFoundError,
    ReportValidationError,
    create_default_template,
)


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


def test_report_round_trips_through_json() -> None:
    report = Report()
    report.add_object(
        ReportObject(
            id="message",
            type="text",
            x=1,
            y=2,
            width=3,
            height=4,
            properties={"text": "Hello"},
        )
    )

    payload = report.to_json()
    loaded = Report.load_from_json(payload)

    assert loaded.to_dict() == report.to_dict()
    assert json.loads(payload)["objects"][0]["type"] == "text"
