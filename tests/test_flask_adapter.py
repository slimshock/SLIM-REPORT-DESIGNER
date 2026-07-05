from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import Flask

from slim_report_core import Report, ReportObject
from slim_report_flask import SlimReportDesigner


def test_flask_adapter_registers_health_route(tmp_path: Path) -> None:
    app, _designer = create_app(tmp_path)

    response = app.test_client().get("/report-designer/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_flask_adapter_creates_lists_and_returns_template(tmp_path: Path) -> None:
    app, _designer = create_app(tmp_path)
    client = app.test_client()

    create_response = client.post("/report-designer/templates/new", json=template_payload())

    assert create_response.status_code == 201
    assert create_response.get_json() == {
        "template": {
            "id": "lab-template",
            "title": "Lab Result",
        }
    }

    list_response = client.get("/report-designer/templates")
    assert list_response.status_code == 200
    assert list_response.get_json() == {
        "templates": [
            {
                "id": "lab-template",
                "title": "Lab Result",
            }
        ]
    }

    designer_response = client.get("/report-designer/templates/lab-template/designer")
    assert designer_response.status_code == 200
    assert designer_response.get_json()["metadata"]["title"] == "Lab Result"


def test_flask_adapter_new_template_get_returns_default_template(tmp_path: Path) -> None:
    app, _designer = create_app(tmp_path)

    response = app.test_client().get("/report-designer/templates/new")

    assert response.status_code == 200
    assert response.get_json()["objects"] == []


def test_flask_preview_uses_provider_and_core_rendering(tmp_path: Path) -> None:
    app, designer = create_app(tmp_path)
    designer.create_template(template_payload())

    @designer.provider("lab_result")
    def lab_result(record_id: str) -> dict[str, Any]:
        return {
            "patient": {"name": f"Patient {record_id}"},
            "result": {"HGB": 14.2},
        }

    response = app.test_client().get("/report-designer/templates/lab-template/preview/123")

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert "Patient 123" in response.get_data(as_text=True)
    assert "14.2" in response.get_data(as_text=True)


def test_flask_pdf_export_delegates_to_core_rendering(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app, designer = create_app(tmp_path)
    designer.create_template(template_payload())
    calls = []

    @designer.provider("lab_result")
    def lab_result(record_id: str) -> dict[str, Any]:
        return {"record_id": record_id}

    def fake_render(
        self: Report,
        data: Any = None,
        *,
        exporter: str = "html",
        context: Any = None,
    ) -> bytes:
        calls.append((data, exporter, context))
        return b"%PDF-1.4 fake"

    monkeypatch.setattr(Report, "render", fake_render)

    response = app.test_client().get("/report-designer/templates/lab-template/export/pdf/ABC")

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.get_data() == b"%PDF-1.4 fake"
    assert calls == [({"record_id": "ABC"}, "pdf", {"record_id": "ABC"})]


def test_flask_adapter_uses_template_provider_mapping(tmp_path: Path) -> None:
    app, designer = create_app(tmp_path)
    app.config["SLIM_REPORT_TEMPLATE_PROVIDERS"] = {"lab-template": "mapped_provider"}
    designer.create_template(template_payload(provider=None))

    @designer.provider("mapped_provider")
    def mapped_provider(record_id: str) -> dict[str, Any]:
        return {
            "patient": {"name": f"Mapped {record_id}"},
            "result": {"HGB": 11.1},
        }

    response = app.test_client().get("/report-designer/templates/lab-template/preview/77")

    assert response.status_code == 200
    assert "Mapped 77" in response.get_data(as_text=True)


def test_flask_adapter_returns_404_for_missing_template(tmp_path: Path) -> None:
    app, _designer = create_app(tmp_path)

    response = app.test_client().get("/report-designer/templates/missing/designer")

    assert response.status_code == 404


def test_flask_adapter_rejects_invalid_template_id(tmp_path: Path) -> None:
    app, _designer = create_app(tmp_path)

    response = app.test_client().get("/report-designer/templates/..%2Fsecret/designer")

    assert response.status_code == 404


def create_app(tmp_path: Path) -> tuple[Flask, SlimReportDesigner]:
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SLIM_REPORT_TEMPLATE_DIR"] = str(tmp_path / "templates")
    designer = SlimReportDesigner()
    designer.init_app(app)
    return app, designer


def template_payload(provider: str | None = "lab_result") -> dict[str, Any]:
    report = Report()
    report.template.metadata.title = "Lab Result"
    report.template.metadata.custom["id"] = "lab-template"
    if provider is not None:
        report.template.metadata.custom["provider"] = provider
    report.add_object(
        ReportObject(
            id="patient_name",
            type="text",
            width=4,
            height=0.5,
            properties={"text": "Patient: {{ patient.name }}"},
        )
    )
    report.add_object(
        ReportObject(
            id="hgb",
            type="field",
            y=0.6,
            width=2,
            height=0.5,
            properties={"field": "result.HGB"},
        )
    )
    return report.to_dict()
