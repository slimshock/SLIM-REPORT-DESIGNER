from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_SRC_DIRS = (
    "packages/slim_report_core/src",
    "packages/slim_report_flask/src",
)

for src_dir in reversed(PACKAGE_SRC_DIRS):
    src_path = str(REPO_ROOT / src_dir)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

from flask import Flask  # noqa: E402

from slim_report_core import Report, ReportObject  # noqa: E402
from slim_report_core.serialization import JSONSerializer  # noqa: E402
from slim_report_flask import SlimReportDesigner  # noqa: E402
from slim_report_flask import extension as extension_module  # noqa: E402


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
    designer_html = designer_response.get_data(as_text=True)
    assert designer_response.status_code == 200
    assert designer_response.mimetype == "text/html"
    assert "Slim Report Designer: Lab Result" in designer_html
    assert "Save" in designer_html
    assert "Preview" in designer_html
    assert "Export PDF" in designer_html
    assert "/report-designer/templates/lab-template/preview/sample" in designer_html
    assert "/report-designer/templates/lab-template/export/pdf/sample" in designer_html


def test_flask_adapter_serves_framework_agnostic_designer_ui(tmp_path: Path) -> None:
    app, _designer = create_app(tmp_path)
    client = app.test_client()

    response = client.get("/report-designer/designer?template=lab-template")
    script_response = client.get("/report-designer/designer-ui/js/designer.js")
    toolbar_response = client.get("/report-designer/designer-ui/js/toolbar.js")
    icons_response = client.get("/report-designer/designer-ui/js/icons.js")
    history_response = client.get("/report-designer/designer-ui/js/history.js")
    css_response = client.get("/report-designer/designer-ui/css/designer.css")

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    html = response.get_data(as_text=True)
    assert "Slim Report Designer" in html
    assert "Click a tool to add it to the page." in html
    assert 'id="selected-object"' in html
    assert 'window.SLIM_REPORT_API_BASE = "/report-designer/api";' in html
    assert script_response.status_code == 200
    assert script_response.mimetype in {"application/javascript", "text/javascript"}
    assert "createCanvasController" in script_response.get_data(as_text=True)
    assert toolbar_response.status_code == 200
    toolbar_js = toolbar_response.get_data(as_text=True)
    assert "icon-action" in toolbar_js
    assert "Export report as PDF" in toolbar_js
    assert icons_response.status_code == 200
    assert "export function icon" in icons_response.get_data(as_text=True)
    assert history_response.status_code == 200
    assert "createVersion" in history_response.get_data(as_text=True)
    assert css_response.status_code == 200
    assert css_response.mimetype == "text/css"
    assert ".inspector-section" in css_response.get_data(as_text=True)


def test_flask_adapter_new_template_get_returns_default_template(tmp_path: Path) -> None:
    app, _designer = create_app(tmp_path)

    response = app.test_client().get("/report-designer/templates/new")

    assert response.status_code == 200
    assert response.get_json()["objects"] == []


def test_flask_designer_api_loads_and_saves_templates(tmp_path: Path) -> None:
    app, designer = create_app(tmp_path)
    designer.create_template(template_payload())
    client = app.test_client()

    get_response = client.get("/report-designer/api/templates/lab-template")
    payload = get_response.get_json()
    payload["metadata"]["name"] = "Canvas Lab Result"
    payload["metadata"].pop("title", None)

    save_response = client.post("/report-designer/api/templates/lab-template", json=payload)

    assert get_response.status_code == 200
    assert payload["objects"][0]["id"] == "patient_name"
    assert save_response.status_code == 200
    assert save_response.get_json()["metadata"]["title"] == "Canvas Lab Result"
    assert designer.get_report("lab-template").metadata.title == "Canvas Lab Result"


def test_flask_designer_api_previews_and_exports_posted_json(tmp_path: Path) -> None:
    app, _designer = create_app(tmp_path)
    payload = {
        "version": "0.1",
        "metadata": {"name": "API Preview"},
        "page": {
            "size": "A4",
            "orientation": "portrait",
            "width": 595,
            "height": 842,
            "unit": "px",
            "background_color": "#ffffff",
            "transparent": False,
        },
        "objects": [
            {
                "id": "title",
                "type": "text",
                "x": 40,
                "y": 40,
                "width": 240,
                "height": 24,
                "text": "Canvas Preview",
                "style": {
                    "font_size": 16,
                    "bold": True,
                    "italic": True,
                    "underline": True,
                    "color": "#005577",
                    "background_color": "#ffeecc",
                    "align": "center",
                },
            },
            {
                "id": "logo",
                "type": "image",
                "x": 40,
                "y": 80,
                "width": 48,
                "height": 48,
                "src": "",
                "alt": "Logo",
                "style": {
                    "object_fit": "contain",
                    "border_width": 1,
                    "border_color": "#000000",
                },
            }
        ],
        "bands": [],
        "assets": [],
    }
    client = app.test_client()

    preview_response = client.post("/report-designer/api/preview", json=payload)
    pdf_response = client.post("/report-designer/api/export/pdf", json=payload)

    assert preview_response.status_code == 200
    assert preview_response.mimetype == "text/html"
    preview_html = preview_response.get_data(as_text=True)
    assert "Canvas Preview" in preview_html
    assert "left: 40.0px" in preview_html
    assert "font-style: italic" in preview_html
    assert "text-decoration: underline" in preview_html
    assert "background: #ffeecc" in preview_html
    assert 'data-slim-object="logo"' in preview_html
    assert "Image" in preview_html
    assert pdf_response.status_code == 200
    assert pdf_response.mimetype == "application/pdf"
    assert pdf_response.get_data().startswith(b"%PDF")


def test_flask_designer_save_route_persists_template_json(tmp_path: Path) -> None:
    app, designer = create_app(tmp_path)
    designer.create_template(template_payload())
    payload = template_payload()
    payload["metadata"]["title"] = "Saved Lab Result"
    payload["objects"][0]["text"] = "SAVED REPORT"

    response = app.test_client().post(
        "/report-designer/templates/lab-template/designer/save",
        json=payload,
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "saved",
        "template": {
            "id": "lab-template",
            "title": "Saved Lab Result",
        },
    }
    saved_report = designer.get_report("lab-template")
    assert saved_report.template.metadata.title == "Saved Lab Result"
    assert (
        JSONSerializer().dump_mapping(saved_report)["objects"][0]["properties"]["text"]
        == "SAVED REPORT"
    )

    @designer.provider("lab_result")
    def lab_result(record_id: str) -> dict[str, Any]:
        return {"patient": {"name": record_id}, "result": {"HGB": "14.5"}}

    preview_response = app.test_client().get(
        "/report-designer/templates/lab-template/preview/sample"
    )
    pdf_response = app.test_client().get(
        "/report-designer/templates/lab-template/export/pdf/sample"
    )
    assert preview_response.status_code == 200
    assert "SAVED REPORT" in preview_response.get_data(as_text=True)
    assert pdf_response.status_code == 200
    assert pdf_response.get_data().startswith(b"%PDF")


def test_flask_designer_save_route_rejects_non_object_payload(tmp_path: Path) -> None:
    app, designer = create_app(tmp_path)
    designer.create_template(template_payload())

    response = app.test_client().post(
        "/report-designer/templates/lab-template/designer/save",
        json=["not", "an", "object"],
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Template payload must be a JSON object."


def test_flask_designer_empty_template_starts_with_sample_objects(tmp_path: Path) -> None:
    app, designer = create_app(tmp_path)
    empty_template = JSONSerializer().dump_mapping(Report())
    empty_template["metadata"]["title"] = "Empty Template"
    empty_template["metadata"]["custom"]["id"] = "empty-template"
    designer.create_template(empty_template)

    response = app.test_client().get("/report-designer/templates/empty-template/designer")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "LABORATORY RESULT" in html
    assert "patient_name" in html
    assert "result.HGB" in html
    assert "result.WBC" in html
    assert "result.PLT" in html


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

    def fake_render_pdf(report: Report, data: dict[str, Any]) -> bytes:
        calls.append((report.metadata.title, data))
        return b"%PDF-1.4 fake"

    monkeypatch.setattr(extension_module, "render_pdf", fake_render_pdf)

    response = app.test_client().get("/report-designer/templates/lab-template/export/pdf/ABC")

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.get_data() == b"%PDF-1.4 fake"
    assert calls == [("Lab Result", {"record_id": "ABC"})]


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
    return JSONSerializer().dump_mapping(report)


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__]))
