"""Production-style Flask integration example for Slim Report Designer."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from flask import Flask, redirect, request

REPO_ROOT = Path(__file__).resolve().parents[2]
for package_src in (
    REPO_ROOT / "packages" / "slim_report_core" / "src",
    REPO_ROOT / "packages" / "slim_report_designer_ui",
    REPO_ROOT / "packages" / "slim_report_flask" / "src",
):
    if str(package_src) not in sys.path:
        sys.path.insert(0, str(package_src))

from slim_report_flask import FileSystemTemplateProvider, SlimReportDesigner  # noqa: E402

TEMPLATE_DIR = REPO_ROOT / "examples" / "flask_app" / "sample_templates"


def create_app() -> Flask:
    """Create a Flask app using the production-oriented extension API."""
    app = Flask(__name__)

    designer = SlimReportDesigner(
        template_provider=FileSystemTemplateProvider(TEMPLATE_DIR, allow_save=False),
        data_provider=lis_data_provider,
        url_prefix="/admin/reports",
        auth_required=demo_auth_required,
        can_view_template=demo_can_view_template,
        can_edit_template=demo_can_edit_template,
        can_export_template=demo_can_export_template,
        csrf_header_name="X-CSRFToken",
        csrf_token_provider=lambda: "demo-csrf-token",
    )
    designer.init_app(app)

    @app.get("/")
    def index():
        return redirect(
            "/admin/reports/designer"
            "?template=complete_sprint5_lab_report&order_id=ORD-2026-0001"
        )

    return app


def lis_data_provider(template_id: str, request_args: Any, request_json: Any) -> dict[str, Any]:
    """Resolve sample LIS data for preview/export requests."""
    order_id = _value_from_request("order_id", request_args, request_json) or "ORD-2026-0001"
    provider = FileSystemTemplateProvider(TEMPLATE_DIR)
    template = provider.get_template(template_id)
    data = dict(template.get("data", {}).get("sample", {}))
    order = dict(data.get("order", {}))
    order["id"] = str(order_id)
    data["order"] = order
    data["barcode_value"] = str(order_id)
    data["qr_value"] = f"https://example.local/verify/{order_id}"
    return data


def demo_auth_required() -> bool:
    """Demo auth hook. Pass ?auth=0 to see a 401 response."""
    return request.args.get("auth", "1") != "0"


def demo_can_view_template(template_id: str) -> bool:
    return bool(template_id)


def demo_can_edit_template(template_id: str) -> bool:
    return False


def demo_can_export_template(template_id: str) -> bool:
    return demo_can_view_template(template_id)


def _value_from_request(name: str, request_args: Any, request_json: Any) -> Any:
    if hasattr(request_args, "get") and request_args.get(name):
        return request_args.get(name)
    if isinstance(request_json, dict):
        if request_json.get(name):
            return request_json[name]
        posted_args = request_json.get("request_args")
        if isinstance(posted_args, dict) and posted_args.get(name):
            return posted_args[name]
    return None


app = create_app()


if __name__ == "__main__":
    app.run(debug=True, port=5001, use_reloader=False)
