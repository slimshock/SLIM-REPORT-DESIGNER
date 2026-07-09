from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

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
from slim_report_core.assets import FileSystemAssetProvider  # noqa: E402
from slim_report_core.serialization import JSONSerializer  # noqa: E402
from slim_report_flask import (  # noqa: E402
    FileSystemTemplateProvider,
    SlimReportDesigner,
    SQLAlchemyTemplateProvider,
    TemplateProvider,
    TemplateStorageError,
)
from slim_report_flask import extension as extension_module  # noqa: E402
from slim_report_flask.blueprint import safe_pdf_filename  # noqa: E402


def test_flask_adapter_registers_health_route(tmp_path: Path) -> None:
    app, _designer = create_app(tmp_path)

    response = app.test_client().get("/report-designer/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_flask_extension_exports_provider_api() -> None:
    assert SlimReportDesigner is not None
    assert FileSystemTemplateProvider is not None
    assert TemplateProvider is not None


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
    default_response = client.get("/report-designer/designer")
    conditional_response = client.get("/report-designer/designer?template=conditional_lab_result")
    script_response = client.get("/report-designer/designer-ui/js/designer.js")
    toolbar_response = client.get("/report-designer/designer-ui/js/toolbar.js")
    icons_response = client.get("/report-designer/designer-ui/js/icons.js")
    history_response = client.get("/report-designer/designer-ui/js/history.js")
    css_response = client.get("/report-designer/designer-ui/css/designer.css")

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert default_response.status_code == 200
    assert conditional_response.status_code == 200
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


def test_flask_adapter_supports_app_factory_custom_prefix_and_runtime_config(
    tmp_path: Path,
) -> None:
    provider = FileSystemTemplateProvider(tmp_path / "templates", allow_save=True)
    app = Flask(__name__)
    app.config["TESTING"] = True
    designer = SlimReportDesigner(
        template_provider=provider,
        url_prefix="/custom/reports",
        csrf_token_provider=lambda: "csrf-123",
        csrf_header_name="X-CSRFToken",
    )
    designer.init_app(app)
    designer.create_template(template_payload())
    client = app.test_client()

    designer_response = client.get("/custom/reports/designer?template=lab-template")
    list_response = client.get("/custom/reports/api/templates")
    js_response = client.get("/custom/reports/designer-ui/js/designer.js")

    assert designer_response.status_code == 200
    html = designer_response.get_data(as_text=True)
    assert 'window.SLIM_REPORT_API_BASE = "/custom/reports/api";' in html
    assert '"templateId": "lab-template"' in html
    assert '"csrfHeaderName": "X-CSRFToken"' in html
    assert '"csrfToken": "csrf-123"' in html
    assert list_response.status_code == 200
    assert list_response.get_json()["templates"][0]["id"] == "lab-template"
    assert list_response.get_json()["templates"][0]["name"] == "Lab Result"
    assert js_response.status_code == 200
    assert js_response.mimetype in {"application/javascript", "text/javascript"}


def test_flask_asset_routes_list_and_serve_assets(tmp_path: Path) -> None:
    asset_dir = tmp_path / "assets"
    asset_dir.mkdir()
    (asset_dir / "clinic_logo.svg").write_text("<svg></svg>", encoding="utf-8")
    app = Flask(__name__)
    app.config["TESTING"] = True
    designer = SlimReportDesigner(
        template_provider=FileSystemTemplateProvider(tmp_path / "templates", allow_save=True),
        asset_provider=FileSystemAssetProvider(
            asset_dir,
            base_url="/report-designer/assets",
        ),
    )
    designer.init_app(app)
    client = app.test_client()

    list_response = client.get("/report-designer/api/assets")
    metadata_response = client.get("/report-designer/api/assets/clinic_logo")
    content_response = client.get("/report-designer/assets/clinic_logo")

    assert list_response.status_code == 200
    assert list_response.get_json()["assets"][0]["id"] == "clinic_logo"
    assert metadata_response.status_code == 200
    assert metadata_response.get_json()["asset"]["url"] == "/report-designer/assets/clinic_logo"
    assert content_response.status_code == 200
    assert content_response.mimetype == "image/svg+xml"
    assert content_response.get_data() == b"<svg></svg>"


def test_flask_asset_routes_support_custom_prefix(tmp_path: Path) -> None:
    asset_dir = tmp_path / "assets"
    asset_dir.mkdir()
    (asset_dir / "clinic_logo.svg").write_text("<svg></svg>", encoding="utf-8")
    app = Flask(__name__)
    app.config["TESTING"] = True
    designer = SlimReportDesigner(
        template_provider=FileSystemTemplateProvider(tmp_path / "templates", allow_save=True),
        asset_provider=FileSystemAssetProvider(
            asset_dir,
            base_url="/admin/reports/assets",
        ),
        url_prefix="/admin/reports",
    )
    designer.init_app(app)

    response = app.test_client().get("/admin/reports/api/assets")
    asset_response = app.test_client().get("/admin/reports/assets/clinic_logo")

    assert response.status_code == 200
    assert response.get_json()["assets"][0]["url"] == "/admin/reports/assets/clinic_logo"
    assert asset_response.status_code == 200


def test_flask_asset_routes_return_clean_errors_and_block_saves(tmp_path: Path) -> None:
    app = Flask(__name__)
    app.config["TESTING"] = True
    designer = SlimReportDesigner(
        template_provider=FileSystemTemplateProvider(tmp_path / "templates", allow_save=True),
        asset_provider=FileSystemAssetProvider(tmp_path / "assets"),
    )
    designer.init_app(app)
    client = app.test_client()

    missing_response = client.get("/report-designer/api/assets/missing_logo")
    invalid_response = client.get("/report-designer/api/assets/..%5Csecret")
    save_response = client.post(
        "/report-designer/api/assets/clinic_logo",
        data=b"<svg></svg>",
        content_type="image/svg+xml",
    )

    assert missing_response.status_code == 404
    assert missing_response.get_json() == {
        "ok": False,
        "error": {
            "code": "asset_not_found",
            "message": "Asset not found: missing_logo",
        },
    }
    assert invalid_response.status_code in {400, 404}
    assert save_response.status_code == 403
    assert save_response.get_json()["error"]["code"] == "asset_forbidden"


def test_flask_preview_uses_asset_provider_for_posted_template(tmp_path: Path) -> None:
    asset_dir = tmp_path / "assets"
    asset_dir.mkdir()
    (asset_dir / "clinic_logo.svg").write_text("<svg></svg>", encoding="utf-8")
    app = Flask(__name__)
    app.config["TESTING"] = True
    designer = SlimReportDesigner(
        template_provider=FileSystemTemplateProvider(tmp_path / "templates", allow_save=True),
        asset_provider=FileSystemAssetProvider(
            asset_dir,
            base_url="/report-designer/assets",
        ),
    )
    designer.init_app(app)
    payload = {
        "version": "0.1",
        "metadata": {"name": "Asset Preview"},
        "page": {"width": 240, "height": 120, "unit": "px"},
        "objects": [
            {
                "id": "logo",
                "type": "image",
                "x": 20,
                "y": 20,
                "width": 120,
                "height": 48,
                "assetId": "clinic_logo",
            }
        ],
        "bands": [],
        "assets": [],
    }

    response = app.test_client().post("/report-designer/api/preview", json=payload)

    assert response.status_code == 200
    assert 'src="/report-designer/assets/clinic_logo"' in response.get_data(as_text=True)


def test_flask_adapter_supports_sqlalchemy_template_provider() -> None:
    sqlalchemy = pytest.importorskip("sqlalchemy")
    from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, Text, create_engine
    from sqlalchemy.orm import declarative_base, sessionmaker

    base = declarative_base()

    class ReportTemplate(base):  # type: ignore[valid-type,misc]
        __tablename__ = "report_templates"

        id = Column(Integer, primary_key=True)
        template_id = Column(String(120), unique=True, nullable=False, index=True)
        name = Column(String(255), nullable=False)
        description = Column(Text, nullable=True)
        category = Column(String(120), nullable=True)
        template_json = Column(JSON, nullable=False)
        sample_data_json = Column(JSON, nullable=True)
        version = Column(Integer, default=1, nullable=False)
        is_active = Column(Boolean, default=True, nullable=False)
        created_at = Column(DateTime, nullable=True)
        updated_at = Column(DateTime, nullable=True)

    engine = create_engine("sqlite:///:memory:")
    base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    provider = SQLAlchemyTemplateProvider(session, ReportTemplate, allow_save=True)
    app = Flask(__name__)
    app.config["TESTING"] = True
    designer = SlimReportDesigner(template_provider=provider)
    designer.init_app(app)
    designer.create_template(template_payload(provider=None))
    client = app.test_client()

    list_response = client.get("/report-designer/api/templates")
    get_response = client.get("/report-designer/api/templates/lab-template")
    preview_response = client.post(
        "/report-designer/api/preview",
        json={
            "template_id": "lab-template",
            "template": get_response.get_json()["template"],
            "data": {"patient": {"name": "DB Patient"}},
        },
    )

    assert sqlalchemy is not None
    assert list_response.status_code == 200
    assert list_response.get_json()["templates"][0]["id"] == "lab-template"
    assert get_response.status_code == 200
    assert get_response.get_json()["template"]["metadata"]["title"] == "Lab Result"
    assert preview_response.status_code == 200
    assert "DB Patient" in preview_response.get_data(as_text=True)


def test_flask_adapter_sqlalchemy_template_provider_saves_database_rows() -> None:
    pytest.importorskip("sqlalchemy")
    from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, Text, create_engine
    from sqlalchemy.orm import declarative_base, sessionmaker

    base = declarative_base()

    class ReportTemplate(base):  # type: ignore[valid-type,misc]
        __tablename__ = "report_templates"

        id = Column(Integer, primary_key=True)
        template_id = Column(String(120), unique=True, nullable=False, index=True)
        name = Column(String(255), nullable=False)
        description = Column(Text, nullable=True)
        category = Column(String(120), nullable=True)
        template_json = Column(JSON, nullable=False)
        sample_data_json = Column(JSON, nullable=True)
        version = Column(Integer, default=1, nullable=False)
        is_active = Column(Boolean, default=True, nullable=False)
        created_at = Column(DateTime, nullable=True)
        updated_at = Column(DateTime, nullable=True)

    engine = create_engine("sqlite:///:memory:")
    base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    provider = SQLAlchemyTemplateProvider(session, ReportTemplate, allow_save=True)
    app = Flask(__name__)
    app.config["TESTING"] = True
    designer = SlimReportDesigner(template_provider=provider)
    designer.init_app(app)
    client = app.test_client()

    create_response = client.post(
        "/report-designer/api/templates/lab-template",
        json=template_payload(),
    )
    saved_row = session.query(ReportTemplate).filter_by(template_id="lab-template").first()

    assert create_response.status_code == 200
    assert saved_row is not None
    assert saved_row.name == "Lab Result"
    assert provider.get_template("lab-template")["metadata"]["title"] == "Lab Result"


def test_filesystem_template_provider_lists_gets_saves_and_rejects_traversal(
    tmp_path: Path,
) -> None:
    provider = FileSystemTemplateProvider(tmp_path, allow_save=True)
    saved = provider.save_template("lab-template", template_payload())

    templates = provider.list_templates()
    loaded = provider.get_template("lab-template")

    assert saved["metadata"]["title"] == "Lab Result"
    assert templates[0]["id"] == "lab-template"
    assert templates[0]["name"] == "Lab Result"
    assert loaded["metadata"]["title"] == "Lab Result"
    assert provider.exists("lab-template")
    assert not provider.exists("../secret")
    with pytest.raises(ValueError):
        provider.get_template("../secret")


def test_filesystem_template_provider_can_disable_saves(tmp_path: Path) -> None:
    provider = FileSystemTemplateProvider(tmp_path, allow_save=False)

    with pytest.raises(PermissionError):
        provider.save_template("lab-template", template_payload())


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


def test_flask_designer_api_unknown_template_returns_json_404(tmp_path: Path) -> None:
    app, _designer = create_app(tmp_path)

    response = app.test_client().get("/report-designer/api/templates/missing-template")

    assert response.status_code == 404
    assert "missing-template" in response.get_json()["error"]


def test_flask_designer_api_save_preserves_repeating_template_data(tmp_path: Path) -> None:
    app, designer = create_app(tmp_path)
    designer.create_template(repeating_template_payload())
    client = app.test_client()

    payload = client.get("/report-designer/api/templates/repeating").get_json()
    payload["metadata"]["title"] = "Saved Repeating"
    response = client.post("/report-designer/api/templates/repeating", json=payload)
    loaded = JSONSerializer().dump_mapping(designer.get_report("repeating"))

    assert response.status_code == 200
    assert response.get_json()["data"]["sample"]["results"][1]["test"] == "HGB"
    assert loaded["data"]["sample"] == payload["data"]["sample"]
    assert loaded["data"]["fields"] == payload["data"]["fields"]


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
            },
        ],
        "bands": [],
        "assets": [],
    }
    client = app.test_client()

    preview_response = client.post("/report-designer/api/preview", json=payload)
    pdf_response = client.post("/report-designer/api/export/pdf", json=payload)

    assert preview_response.status_code == 200
    assert preview_response.mimetype == "text/html"
    assert preview_response.headers["X-Slim-Report-Object-Count"] == "2"
    assert preview_response.headers["X-Slim-Report-Template-Name"] == "API Preview"
    assert preview_response.headers["X-Slim-Report-Renderer"] == "html"
    assert preview_response.headers["X-Slim-Report-Page-Unit"] == "px"
    assert preview_response.headers["X-Slim-Report-Page-Width"] == "595.0"
    assert preview_response.headers["X-Slim-Report-Page-Height"] == "842.0"
    preview_html = preview_response.get_data(as_text=True)
    assert "Canvas Preview" in preview_html
    assert "left: 40.0px" in preview_html
    assert "font-style: italic" in preview_html
    assert "text-decoration: underline" in preview_html
    assert "background: #ffeecc" in preview_html
    assert 'data-slim-object="logo"' in preview_html
    assert ">Image<" not in preview_html
    assert pdf_response.status_code == 200
    assert pdf_response.mimetype == "application/pdf"
    assert pdf_response.headers["X-Slim-Report-Object-Count"] == "2"
    assert pdf_response.headers["X-Slim-Report-Renderer"] == "pdf"
    assert pdf_response.headers["Content-Disposition"] == 'attachment; filename="API-Preview.pdf"'
    assert pdf_response.headers["X-Slim-Report-Page-Unit"] == "px"
    assert pdf_response.get_data().startswith(b"%PDF")


def test_flask_preview_export_and_print_support_band_based_templates(tmp_path: Path) -> None:
    app, designer = create_app(tmp_path)
    template = band_based_template_payload()
    designer.create_template(template)
    client = app.test_client()

    posted_preview = client.post(
        "/report-designer/api/preview",
        json={"template_id": "band-template", "template": template},
    )
    posted_pdf = client.post(
        "/report-designer/api/export/pdf",
        json={"template_id": "band-template", "template": template},
    )
    print_response = client.get("/report-designer/print/band-template")
    get_pdf_response = client.get("/report-designer/export/pdf/band-template")

    assert posted_preview.status_code == 200
    assert posted_preview.headers["X-Slim-Report-Object-Count"] == "2"
    assert "Band Based Report" in posted_preview.get_data(as_text=True)
    assert "Band Patient" in posted_preview.get_data(as_text=True)
    assert posted_pdf.status_code == 200
    assert posted_pdf.get_data().startswith(b"%PDF")
    assert print_response.status_code == 200
    assert "Band Based Report" in print_response.get_data(as_text=True)
    assert get_pdf_response.status_code == 200
    assert get_pdf_response.get_data().startswith(b"%PDF")


def test_flask_designer_api_uses_posted_template_sample_data(tmp_path: Path) -> None:
    app, _designer = create_app(tmp_path)
    payload = {
        "version": "0.1",
        "metadata": {"name": "Sample Data Preview"},
        "page": {
            "size": "A4",
            "orientation": "portrait",
            "width": 595,
            "height": 842,
            "unit": "px",
        },
        "objects": [
            {
                "id": "patient",
                "type": "field",
                "x": 40,
                "y": 40,
                "width": 180,
                "height": 24,
                "binding": "patient.name",
            }
        ],
        "data": {"sample": {"patient": {"name": "Sample Patient"}}},
        "bands": [],
        "assets": [],
    }

    response = app.test_client().post("/report-designer/api/preview", json=payload)

    assert response.status_code == 200
    assert "Sample Patient" in response.get_data(as_text=True)


def test_flask_designer_api_preview_and_export_use_explicit_data_payload(tmp_path: Path) -> None:
    app, _designer = create_app(tmp_path)
    template = repeating_template_payload()
    template["data"]["sample"] = {"results": [{"test": "WRONG", "result": "0.00"}]}
    data = {
        "results": [
            {"test": "WBC", "result": "7.10"},
            {"test": "HGB", "result": "14.20"},
        ]
    }
    request_payload = {
        "template_id": "repeating",
        "template": template,
        "data": data,
    }
    client = app.test_client()

    preview_response = client.post("/report-designer/api/preview", json=request_payload)
    pdf_response = client.post("/report-designer/api/export/pdf", json=request_payload)

    assert preview_response.status_code == 200
    html = preview_response.get_data(as_text=True)
    assert "WBC" in html
    assert "7.10" in html
    assert "HGB" in html
    assert "14.20" in html
    assert "WRONG" not in html
    assert preview_response.headers["X-Slim-Report-Has-Data-Sample"] == "true"
    assert preview_response.headers["X-Slim-Report-Repeat-Data-Path"] == "results"
    assert preview_response.headers["X-Slim-Report-Repeat-Row-Count"] == "2"
    assert pdf_response.status_code == 200
    assert pdf_response.get_data().startswith(b"%PDF")
    assert pdf_response.headers["X-Slim-Report-Repeat-Row-Count"] == "2"


def test_flask_designer_api_preview_falls_back_to_data_provider(tmp_path: Path) -> None:
    def data_provider(template_id: str, request_args: Any, request_json: Any) -> dict[str, Any]:
        assert template_id == "lab-template"
        return {"patient": {"name": request_json["request_args"]["patient"]}}

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SLIM_REPORT_TEMPLATE_DIR"] = str(tmp_path / "templates")
    designer = SlimReportDesigner(data_provider=data_provider)
    designer.init_app(app)
    designer.create_template(template_payload(provider=None))

    response = app.test_client().post(
        "/report-designer/api/preview",
        json={
            "template_id": "lab-template",
            "template": template_payload(provider=None),
            "request_args": {"patient": "Provider Patient"},
        },
    )

    assert response.status_code == 200
    assert "Provider Patient" in response.get_data(as_text=True)


def test_flask_designer_api_preview_falls_back_to_template_sample(tmp_path: Path) -> None:
    app, _designer = create_app(tmp_path)
    template = template_payload(provider=None)
    template["data"] = {"sample": {"patient": {"name": "Sample Fallback"}}}

    response = app.test_client().post(
        "/report-designer/api/preview",
        json={"template_id": "lab-template", "template": template},
    )

    assert response.status_code == 200
    assert "Sample Fallback" in response.get_data(as_text=True)


def test_flask_designer_api_preview_falls_back_to_provider_sample_data(tmp_path: Path) -> None:
    provider = FileSystemTemplateProvider(tmp_path / "templates", allow_save=True)
    template = template_payload(provider=None)
    template["data"] = {"sample": {"patient": {"name": "Provider Sample"}}}
    provider.save_template("lab-template", template)
    app = Flask(__name__)
    app.config["TESTING"] = True
    designer = SlimReportDesigner(template_provider=provider)
    designer.init_app(app)

    response = app.test_client().post(
        "/report-designer/api/preview",
        json={
            "template_id": "lab-template",
            "template": {
                **template_payload(provider=None),
                "data": {"sample": {"patient": {"name": "Posted Sample"}}},
            },
        },
    )

    assert response.status_code == 200
    assert "Provider Sample" in response.get_data(as_text=True)
    assert "Posted Sample" not in response.get_data(as_text=True)


def test_flask_designer_api_data_provider_exception_returns_clean_error(tmp_path: Path) -> None:
    def data_provider(template_id: str, request_args: Any, request_json: Any) -> dict[str, Any]:
        raise RuntimeError(f"Data unavailable for {template_id}")

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SLIM_REPORT_TEMPLATE_DIR"] = str(tmp_path / "templates")
    designer = SlimReportDesigner(data_provider=data_provider)
    designer.init_app(app)

    response = app.test_client().post(
        "/report-designer/api/preview",
        json={"template_id": "lab-template", "template": template_payload(provider=None)},
    )

    assert response.status_code == 500
    payload = response.get_json()
    assert payload["ok"] is False
    assert payload["error_detail"]["code"] == "server_error"
    assert "Data unavailable" in payload["error"]


def test_flask_designer_provider_exception_returns_clean_storage_error() -> None:
    class FailingProvider:
        allow_save = True

        def list_templates(self) -> list[dict[str, Any]]:
            raise TemplateStorageError("Could not connect to MySQL.")

        def get_template(self, template_id: str) -> dict[str, Any]:
            raise TemplateStorageError("Could not connect to MySQL.")

        def save_template(self, template_id: str, template: dict[str, Any]) -> dict[str, Any]:
            raise TemplateStorageError("Could not connect to MySQL.")

        def exists(self, template_id: str) -> bool:
            return False

    app = Flask(__name__)
    app.config["TESTING"] = True
    designer = SlimReportDesigner(template_provider=FailingProvider())
    designer.init_app(app)

    response = app.test_client().get("/report-designer/api/templates")

    assert response.status_code == 500
    payload = response.get_json()
    assert payload["ok"] is False
    assert payload["error_detail"]["code"] == "template_storage_error"
    assert payload["error_detail"]["message"] == "Could not connect to MySQL."


def test_flask_auth_hook_blocks_designer_and_api(tmp_path: Path) -> None:
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SLIM_REPORT_TEMPLATE_DIR"] = str(tmp_path / "templates")
    designer = SlimReportDesigner(auth_required=lambda: False)
    designer.init_app(app)

    designer_response = app.test_client().get("/report-designer/designer")
    api_response = app.test_client().get("/report-designer/api/templates")

    assert designer_response.status_code == 401
    assert api_response.status_code == 401
    assert api_response.get_json()["error_detail"]["code"] == "unauthorized"


def test_flask_permission_hooks_block_view_edit_and_export(tmp_path: Path) -> None:
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SLIM_REPORT_TEMPLATE_DIR"] = str(tmp_path / "templates")
    designer = SlimReportDesigner(
        can_view_template=lambda template_id: template_id != "blocked",
        can_edit_template=lambda template_id: False,
        can_export_template=lambda template_id: False,
    )
    designer.init_app(app)
    designer.create_template(
        {**template_payload(), "metadata": {"title": "Allowed", "custom": {"id": "allowed"}}}
    )
    designer.create_template(
        {**template_payload(), "metadata": {"title": "Blocked", "custom": {"id": "blocked"}}}
    )
    client = app.test_client()

    view_response = client.get("/report-designer/api/templates/blocked")
    edit_response = client.post(
        "/report-designer/api/templates/allowed",
        json={"template": template_payload(provider=None)},
    )
    export_response = client.post(
        "/report-designer/api/export/pdf",
        json={"template_id": "allowed", "template": template_payload(provider=None)},
    )
    print_response = client.get("/report-designer/print/blocked")
    get_export_response = client.get("/report-designer/export/pdf/allowed")

    assert view_response.status_code == 403
    assert view_response.get_json()["error_detail"]["code"] == "forbidden"
    assert edit_response.status_code == 403
    assert export_response.status_code == 403
    assert print_response.status_code == 403
    assert get_export_response.status_code == 403


def test_flask_designer_api_missing_render_data_does_not_crash(tmp_path: Path) -> None:
    app, _designer = create_app(tmp_path)
    payload = {
        "version": "0.1",
        "metadata": {"name": "No Data Preview"},
        "page": {
            "size": "A4",
            "orientation": "portrait",
            "width": 595,
            "height": 842,
            "unit": "px",
        },
        "objects": [
            {
                "id": "patient",
                "type": "field",
                "x": 40,
                "y": 40,
                "width": 180,
                "height": 24,
                "binding": "patient.name",
            }
        ],
        "bands": [],
        "assets": [],
    }

    response = app.test_client().post("/report-designer/api/preview", json=payload)

    assert response.status_code == 200


def test_flask_designer_api_rejects_empty_preview_and_export(tmp_path: Path) -> None:
    app, _designer = create_app(tmp_path)
    payload = {
        "version": "0.1",
        "metadata": {"name": "Empty"},
        "page": {
            "size": "A4",
            "orientation": "portrait",
            "width": 595,
            "height": 842,
            "unit": "px",
        },
        "objects": [],
        "bands": [],
        "assets": [],
    }
    client = app.test_client()

    preview_response = client.post("/report-designer/api/preview", json=payload)
    pdf_response = client.post("/report-designer/api/export/pdf", json=payload)

    assert preview_response.status_code == 400
    assert "at least one object" in preview_response.get_json()["error"]
    assert pdf_response.status_code == 400
    assert "at least one object" in pdf_response.get_json()["error"]
    assert pdf_response.get_json()["type"] == "ValueError"


def test_flask_designer_api_rejects_empty_band_based_preview(tmp_path: Path) -> None:
    app, _designer = create_app(tmp_path)
    payload = {
        "version": "0.1",
        "metadata": {"name": "Empty Bands"},
        "page": {"width": 595, "height": 842, "unit": "px"},
        "bands": [
            {"id": "page_header", "type": "pageHeader", "height": 80, "objects": []},
            {"id": "detail", "type": "detail", "height": 700, "objects": []},
        ],
        "assets": [],
    }

    response = app.test_client().post("/report-designer/api/preview", json=payload)

    assert response.status_code == 400
    assert "at least one object" in response.get_json()["error"]


def test_flask_export_uses_page_print_filename_and_safe_slug(tmp_path: Path) -> None:
    app, _designer = create_app(tmp_path)
    payload = {
        **template_payload(provider=None),
        "metadata": {"name": "Unsafe Export"},
    }
    payload["page"]["print"] = {"default_filename": 'CBC: Result/July*08?.pdf'}

    response = app.test_client().post("/report-designer/api/export/pdf", json=payload)

    assert response.status_code == 200
    assert (
        response.headers["Content-Disposition"]
        == 'attachment; filename="CBC-Result-July-08.pdf"'
    )


def test_safe_pdf_filename_removes_windows_invalid_characters() -> None:
    assert safe_pdf_filename('CBC: Result/July*08?.pdf') == "CBC-Result-July-08.pdf"
    assert safe_pdf_filename("CON") == "report.pdf"


def test_flask_helper_api_renders_with_standard_data_priority(tmp_path: Path) -> None:
    calls: list[str] = []

    def data_provider(template_id: str, request_args: Any, request_json: Any) -> dict[str, Any]:
        calls.append(str(request_args.get("order_id")))
        return {"patient": {"name": f"Provider {request_args.get('order_id')}"}}

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SLIM_REPORT_TEMPLATE_DIR"] = str(tmp_path / "templates")
    designer = SlimReportDesigner(data_provider=data_provider)
    designer.init_app(app)
    designer.create_template(template_payload(provider=None))

    explicit_html = designer.render_template_html(
        "lab-template",
        data={"patient": {"name": "Explicit Patient"}},
        request_args={"order_id": "43"},
    )
    provider_html = designer.render_template_html(
        "lab-template",
        request_args={"order_id": "44"},
    )
    pdf = designer.render_template_pdf(
        "lab-template",
        data={"patient": {"name": "PDF Patient"}},
    )

    assert "Explicit Patient" in explicit_html
    assert "Provider 44" in provider_html
    assert pdf.startswith(b"%PDF")
    assert calls == ["44"]


def test_flask_helper_api_falls_back_to_template_sample_data(tmp_path: Path) -> None:
    _app, designer = create_app(tmp_path)
    payload = template_payload(provider=None)
    payload["data"] = {"sample": {"patient": {"name": "Template Sample"}}}
    designer.create_template(payload)

    html = designer.render_template_html("lab-template")

    assert "Template Sample" in html


def test_flask_print_route_renders_query_data_and_auto_print(tmp_path: Path) -> None:
    captured_args: list[str] = []

    def data_provider(template_id: str, request_args: Any, request_json: Any) -> dict[str, Any]:
        captured_args.append(str(request_args.get("order_id")))
        return {"patient": {"name": f"Order {request_args.get('order_id')}"}}

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SLIM_REPORT_TEMPLATE_DIR"] = str(tmp_path / "templates")
    designer = SlimReportDesigner(data_provider=data_provider)
    designer.init_app(app)
    designer.create_template(template_payload(provider=None))

    response = app.test_client().get(
        "/report-designer/print/lab-template?order_id=43&auto_print=1"
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert "Order 43" in html
    assert "window.print()" in html
    assert "slim-report-print-route-css" in html
    assert '<div class="slim-report-preview-toolbar">' not in html
    assert captured_args == ["43"]


def test_flask_get_pdf_route_supports_filename_provider_and_disposition(tmp_path: Path) -> None:
    def data_provider(template_id: str, request_args: Any, request_json: Any) -> dict[str, Any]:
        return {"patient": {"name": f"Order {request_args.get('order_id')}"}}

    def filename_provider(template_id: str, data: dict[str, Any], request_args: Any) -> str:
        return f"lab/result-{request_args.get('order_id')}"

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SLIM_REPORT_TEMPLATE_DIR"] = str(tmp_path / "templates")
    designer = SlimReportDesigner(
        data_provider=data_provider,
        filename_provider=filename_provider,
    )
    designer.init_app(app)
    designer.create_template(template_payload(provider=None))
    client = app.test_client()

    inline_response = client.get("/report-designer/export/pdf/lab-template?order_id=43")
    download_response = client.get(
        "/report-designer/export/pdf/lab-template?order_id=43&download=1"
    )
    override_response = client.get(
        "/report-designer/export/pdf/lab-template?filename=Unsafe/Name*42"
    )

    assert inline_response.status_code == 200
    assert inline_response.mimetype == "application/pdf"
    assert inline_response.get_data().startswith(b"%PDF")
    assert inline_response.headers["Content-Disposition"] == 'inline; filename="lab-result-43.pdf"'
    assert download_response.headers["Content-Disposition"] == (
        'attachment; filename="lab-result-43.pdf"'
    )
    assert override_response.headers["Content-Disposition"] == (
        'inline; filename="Unsafe-Name-42.pdf"'
    )


def test_flask_get_print_and_pdf_routes_return_clean_missing_template_errors(
    tmp_path: Path,
) -> None:
    app, _designer = create_app(tmp_path)
    client = app.test_client()

    print_response = client.get(
        "/report-designer/print/missing",
        headers={"Accept": "application/json"},
    )
    pdf_response = client.get(
        "/report-designer/export/pdf/missing",
        headers={"Accept": "application/json"},
    )

    assert print_response.status_code == 404
    assert print_response.get_json()["error_detail"]["code"] == "template_not_found"
    assert pdf_response.status_code == 404
    assert pdf_response.get_json()["error_detail"]["code"] == "template_not_found"


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


def test_flask_preview_and_pdf_support_repeating_detail_template(tmp_path: Path) -> None:
    app, designer = create_app(tmp_path)
    payload = {
        "version": "1.0",
        "metadata": {"title": "Repeating", "custom": {"id": "repeating"}},
        "page": {"width": 595, "height": 842, "unit": "px"},
        "objects": [
            {
                "id": "test",
                "type": "field",
                "x": 40,
                "y": 140,
                "width": 100,
                "height": 18,
                "binding": "test",
                "band": "detail",
            },
            {
                "id": "value",
                "type": "field",
                "x": 160,
                "y": 140,
                "width": 100,
                "height": 18,
                "binding": "results[].value",
                "band": "detail",
            },
        ],
        "bands": [
            {
                "id": "detail",
                "type": "detail",
                "name": "Detail",
                "y": 100,
                "height": 700,
                "repeat": {
                    "enabled": True,
                    "data_path": "results",
                    "row_height": 24,
                    "preview_rows": 10,
                    "empty_message": "No results",
                },
            }
        ],
        "data": {"sample": {"results": flask_many_results()}},
        "assets": [],
    }
    designer.create_template(payload)
    client = app.test_client()

    preview_response = client.get("/report-designer/templates/repeating/preview/sample")
    pdf_response = client.get("/report-designer/templates/repeating/export/pdf/sample")

    assert preview_response.status_code == 200
    assert "WBC" in preview_response.get_data(as_text=True)
    assert "Nitrite" in preview_response.get_data(as_text=True)
    assert int(preview_response.headers["X-Slim-Report-Page-Count"]) > 1
    assert preview_response.headers["X-Slim-Report-Repeated-Row-Count"] == "36"
    assert pdf_response.status_code == 200
    assert pdf_response.get_data().startswith(b"%PDF")
    assert int(pdf_response.headers["X-Slim-Report-Page-Count"]) > 1


def test_flask_preview_and_pdf_support_basic_table_template(tmp_path: Path) -> None:
    app, designer = create_app(tmp_path)
    designer.create_template(table_template_payload())

    @designer.provider("table_lab_result")
    def table_provider(record_id: str) -> dict[str, Any]:
        return {
            "results": flask_many_results(),
            "order": {"id": record_id},
        }

    client = app.test_client()
    preview_response = client.get("/report-designer/templates/table_lab_result/preview/sample")
    pdf_response = client.get("/report-designer/templates/table_lab_result/export/pdf/sample")

    assert preview_response.status_code == 200
    html = preview_response.get_data(as_text=True)
    assert "WBC" in html
    assert "7.10" in html
    assert "Nitrite" in html
    assert int(preview_response.headers["X-Slim-Report-Page-Count"]) > 1
    assert preview_response.headers["X-Slim-Report-Table-Row-Count"] == "36"
    assert pdf_response.status_code == 200
    assert pdf_response.mimetype == "application/pdf"
    assert pdf_response.get_data().startswith(b"%PDF")
    assert len(pdf_response.get_data()) > 1000
    assert int(pdf_response.headers["X-Slim-Report-Page-Count"]) > 1


def test_flask_preview_and_pdf_support_barcode_qr_template(tmp_path: Path) -> None:
    app, designer = create_app(tmp_path)
    designer.create_template(barcode_qr_template_payload())

    @designer.provider("barcode_qr_lab_result")
    def barcode_qr_provider(record_id: str) -> dict[str, Any]:
        return {
            "order": {"id": record_id},
            "patient": {"name": "JUAN DELA CRUZ", "patient_no": "P-00001234"},
        }

    client = app.test_client()
    preview_response = client.get(
        "/report-designer/templates/barcode_qr_lab_result/preview/ORDER-42"
    )
    pdf_response = client.get(
        "/report-designer/templates/barcode_qr_lab_result/export/pdf/ORDER-42"
    )

    assert preview_response.status_code == 200
    html = preview_response.get_data(as_text=True)
    assert "ORDER-42" in html
    assert 'data-slim-object="barcode_order_id"' in html
    assert 'data-slim-object="qr_order_id"' in html
    assert pdf_response.status_code == 200
    assert pdf_response.mimetype == "application/pdf"
    assert pdf_response.get_data().startswith(b"%PDF")
    assert len(pdf_response.get_data()) > 1000


def test_flask_preview_and_pdf_support_grouped_template(tmp_path: Path) -> None:
    app, designer = create_app(tmp_path)
    designer.create_template(grouped_template_payload())

    @designer.provider("grouped_lab_result")
    def grouped_provider(record_id: str) -> dict[str, Any]:
        return {
            "order": {"id": record_id},
            "results": [
                {"section": "HEMATOLOGY", "test": "WBC", "value": "7.10"},
                {"section": "HEMATOLOGY", "test": "HGB", "value": "14.20"},
                {"section": "CHEMISTRY", "test": "FBS", "value": "95"},
            ],
        }

    client = app.test_client()
    preview_response = client.get("/report-designer/templates/grouped_lab_result/preview/ORDER-42")
    pdf_response = client.get("/report-designer/templates/grouped_lab_result/export/pdf/ORDER-42")

    assert preview_response.status_code == 200
    html = preview_response.get_data(as_text=True)
    assert "HEMATOLOGY" in html
    assert "CHEMISTRY" in html
    assert "WBC" in html
    assert pdf_response.status_code == 200
    assert pdf_response.mimetype == "application/pdf"
    assert pdf_response.get_data().startswith(b"%PDF")
    assert len(pdf_response.get_data()) > 1000


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


def flask_many_results() -> list[dict[str, str]]:
    rows = [
        {
            "test": "WBC" if index == 1 else f"Test {index:02d}",
            "result": "7.10" if index == 1 else str(index),
            "value": "7.10" if index == 1 else str(index),
            "unit": "mg/dL",
        }
        for index in range(1, 36)
    ]
    rows.append({"test": "Nitrite", "result": "Negative", "value": "Negative", "unit": ""})
    return rows


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


def band_based_template_payload() -> dict[str, Any]:
    return {
        "version": "1.0",
        "metadata": {"title": "Band Based", "custom": {"id": "band-template"}},
        "page": {"width": 595, "height": 842, "unit": "px"},
        "bands": [
            {
                "id": "page_header",
                "type": "pageHeader",
                "height": 80,
                "objects": [
                    {
                        "id": "report_title",
                        "type": "text",
                        "x": 40,
                        "y": 24,
                        "width": 240,
                        "height": 24,
                        "text": "Band Based Report",
                        "band": "pageHeader",
                    }
                ],
            },
            {
                "id": "detail",
                "type": "detail",
                "height": 700,
                "objects": [
                    {
                        "id": "patient_name",
                        "type": "field",
                        "x": 40,
                        "y": 120,
                        "width": 240,
                        "height": 20,
                        "binding": "patient.name",
                        "bandId": "detail",
                    }
                ],
            },
        ],
        "data": {"sample": {"patient": {"name": "Band Patient"}}},
        "assets": [],
    }


def repeating_template_payload() -> dict[str, Any]:
    return {
        "version": "1.0",
        "metadata": {"title": "Repeating", "custom": {"id": "repeating"}},
        "page": {"width": 595, "height": 842, "unit": "px"},
        "objects": [
            {
                "id": "test",
                "type": "field",
                "x": 40,
                "y": 140,
                "width": 100,
                "height": 18,
                "binding": "test",
                "band": "detail",
            },
            {
                "id": "result",
                "type": "field",
                "x": 160,
                "y": 140,
                "width": 100,
                "height": 18,
                "binding": "result",
                "band": "detail",
            },
        ],
        "bands": [
            {
                "id": "detail",
                "type": "detail",
                "name": "Detail",
                "y": 100,
                "height": 700,
                "repeat": {
                    "enabled": True,
                    "data_path": "results",
                    "row_height": 24,
                    "preview_rows": 10,
                    "empty_message": "No results",
                },
            }
        ],
        "data": {
            "sample": {
                "results": [
                    {"test": "WBC", "result": "7.10"},
                    {"test": "HGB", "result": "14.20"},
                ]
            },
            "fields": [
                {"path": "results[]", "label": "Results", "type": "array", "sample": "2 rows"},
                {"path": "results[].test", "label": "Test", "type": "string", "sample": "WBC"},
                {"path": "results[].result", "label": "Result", "type": "string", "sample": "7.10"},
            ],
        },
        "assets": [],
    }


def table_template_payload() -> dict[str, Any]:
    return {
        "version": "1.0",
        "metadata": {
            "title": "Table Lab Result",
            "custom": {
                "id": "table_lab_result",
                "provider": "table_lab_result",
            },
        },
        "page": {"width": 595, "height": 842, "unit": "px"},
        "objects": [
            {
                "id": "results_table",
                "type": "table",
                "x": 40,
                "y": 120,
                "width": 300,
                "height": 120,
                "data_path": "results",
                "columns": [
                    {"id": "test", "label": "Test", "binding": "test", "width": 150},
                    {"id": "result", "label": "Result", "binding": "result", "width": 90},
                    {"id": "unit", "label": "Unit", "binding": "unit", "width": 80},
                ],
                "header": {"visible": True, "height": 24},
                "row": {"height": 22},
                "border": {"width": 1, "color": "#d1d5db"},
            }
        ],
        "bands": [],
        "data": {"sample": {"results": [{"test": "WBC", "result": "7.10", "unit": "10^9/L"}]}},
        "assets": [],
    }


def grouped_template_payload() -> dict[str, Any]:
    return {
        "version": "1.0",
        "metadata": {
            "title": "Grouped Lab Result",
            "custom": {"id": "grouped_lab_result", "provider": "grouped_lab_result"},
        },
        "page": {"width": 595, "height": 842, "unit": "px"},
        "objects": [
            {
                "id": "group_name",
                "type": "field",
                "x": 40,
                "y": 108,
                "width": 160,
                "height": 18,
                "binding": "group.value",
                "band": "group_header_results",
            },
            {
                "id": "row_test",
                "type": "field",
                "x": 40,
                "y": 140,
                "width": 120,
                "height": 18,
                "binding": "test",
                "band": "detail",
            },
            {
                "id": "group_count",
                "type": "field",
                "x": 40,
                "y": 758,
                "width": 80,
                "height": 18,
                "binding": "group.count",
                "band": "group_footer_results",
            },
        ],
        "bands": [
            {"id": "page_header", "type": "page_header", "y": 0, "height": 100},
            {
                "id": "group_header_results",
                "type": "group_header",
                "y": 100,
                "height": 28,
                "group": {
                    "id": "results_section",
                    "data_path": "results",
                    "field": "section",
                    "sort": "none",
                },
            },
            {
                "id": "detail",
                "type": "detail",
                "y": 128,
                "height": 628,
                "repeat": {"enabled": True, "data_path": "results", "row_height": 24},
            },
            {
                "id": "group_footer_results",
                "type": "group_footer",
                "y": 756,
                "height": 24,
                "group": {"id": "results_section"},
            },
            {"id": "page_footer", "type": "page_footer", "y": 780, "height": 62},
        ],
        "data": {"sample": {"results": [{"section": "HEMATOLOGY", "test": "WBC"}]}},
        "assets": [],
    }


def barcode_qr_template_payload() -> dict[str, Any]:
    return {
        "version": "1.0",
        "metadata": {
            "title": "Barcode QR Lab Result",
            "custom": {
                "id": "barcode_qr_lab_result",
                "provider": "barcode_qr_lab_result",
            },
        },
        "page": {"width": 595, "height": 842, "unit": "px"},
        "objects": [
            {
                "id": "barcode_order_id",
                "type": "barcode",
                "x": 40,
                "y": 40,
                "width": 160,
                "height": 48,
                "value": "1234567890",
                "binding": "order.id",
                "format": "code128",
                "show_text": True,
            },
            {
                "id": "qr_order_id",
                "type": "qrcode",
                "x": 230,
                "y": 32,
                "width": 80,
                "height": 80,
                "value": "https://example.com",
                "binding": "order.id",
                "error_correction": "M",
            },
        ],
        "bands": [],
        "data": {"sample": {"order": {"id": "ORDER-1001"}}},
        "assets": [],
    }


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__]))
