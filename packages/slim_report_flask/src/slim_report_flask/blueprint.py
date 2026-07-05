"""Flask blueprint routes for Slim Report Designer."""

from __future__ import annotations

import json
import mimetypes
from typing import TYPE_CHECKING, Any

from flask import Blueprint, Response, jsonify, request, url_for

from slim_report_core import ExporterError, Report, SlimReportError, create_default_template
from slim_report_core.serialization import JSONSerializer
from slim_report_designer_ui import static_file

from .designer import render_designer_page, template_for_designer

if TYPE_CHECKING:
    from .extension import SlimReportDesigner


def create_blueprint(designer: SlimReportDesigner) -> Blueprint:
    """Create the report designer blueprint."""
    blueprint = Blueprint("slim_report_designer", __name__)

    @blueprint.get("/health")
    def health() -> Response:
        return jsonify({"status": "ok"})

    @blueprint.get("/templates")
    def templates() -> Response:
        return jsonify({"templates": [item.to_dict() for item in designer.list_templates()]})

    @blueprint.route("/templates/new", methods=["GET", "POST"])
    def new_template() -> tuple[Response, int] | Response:
        if request.method == "GET":
            return jsonify(create_default_template().to_dict())

        payload = request.get_json(silent=True)
        if payload is not None and not isinstance(payload, dict):
            return jsonify({"error": "Template payload must be a JSON object."}), 400

        record = designer.create_template(payload)
        return jsonify({"template": record.to_dict()}), 201

    @blueprint.get("/templates/<template_id>/designer")
    def designer_template(template_id: str) -> Response:
        report = designer.get_report(template_id)
        editable_template = template_for_designer(JSONSerializer().dump_mapping(report))
        html = render_designer_page(
            template_id=template_id,
            template=editable_template,
            save_url=url_for(
                "slim_report_designer.save_designer_template",
                template_id=template_id,
            ),
            preview_url=url_for(
                "slim_report_designer.preview",
                template_id=template_id,
                record_id="sample",
            ),
            pdf_url=url_for(
                "slim_report_designer.export_pdf",
                template_id=template_id,
                record_id="sample",
            ),
        )
        return Response(html, mimetype="text/html")

    @blueprint.get("/designer")
    def canvas_designer() -> Response:
        html = static_file("index.html").read_text(encoding="utf-8")
        asset_base = url_for(
            "slim_report_designer.designer_ui_asset",
            asset_path="index.html",
        ).rsplit("/", 1)[0]
        api_base = url_for("slim_report_designer.api_templates_root").rsplit(
            "/templates",
            1,
        )[0]
        config = (
            f'<base href="{asset_base}/">\n'
            "<script>"
            f"window.SLIM_REPORT_API_BASE = {json.dumps(api_base)};"
            "</script>"
        )
        html = html.replace("<head>\n", f"<head>\n{config}\n", 1)
        return Response(html, mimetype="text/html")

    @blueprint.get("/designer-ui/<path:asset_path>")
    def designer_ui_asset(asset_path: str) -> Response:
        return _static_response(asset_path)

    @blueprint.post("/templates/<template_id>/designer/save")
    def save_designer_template(template_id: str) -> tuple[Response, int]:
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "Template payload must be a JSON object."}), 400

        record = designer.save_template(template_id, payload)
        return jsonify({"status": "saved", "template": record.to_dict()}), 200

    @blueprint.get("/api/templates")
    def api_templates_root() -> Response:
        return jsonify({"templates": [item.to_dict() for item in designer.list_templates()]})

    @blueprint.get("/api/templates/<template_id>")
    def api_template(template_id: str) -> Response:
        report = designer.get_report(template_id)
        return jsonify(JSONSerializer().dump_mapping(report))

    @blueprint.post("/api/templates/<template_id>")
    def save_api_template(template_id: str) -> tuple[Response, int]:
        payload = request_template_payload()
        record = designer.save_template(template_id, normalize_template_payload(payload))
        report = designer.get_report(record.id)
        return jsonify(JSONSerializer().dump_mapping(report)), 200

    @blueprint.post("/api/preview")
    def api_preview() -> Response:
        payload = request_template_payload()
        data = request_template_data()
        report = load_report_from_payload(normalize_template_payload(payload))
        return Response(report.render_html(data), mimetype="text/html")

    @blueprint.post("/api/export/pdf")
    def api_export_pdf() -> Response:
        payload = request_template_payload()
        data = request_template_data()
        report = load_report_from_payload(normalize_template_payload(payload))
        return Response(
            report.render_pdf(data),
            mimetype="application/pdf",
            headers={"Content-Disposition": 'attachment; filename="report-template.pdf"'},
        )

    @blueprint.get("/templates/<template_id>/preview/<record_id>")
    def preview(template_id: str, record_id: str) -> Response:
        html = designer.render_preview(template_id, record_id)
        return Response(html, mimetype="text/html")

    @blueprint.get("/templates/<template_id>/export/pdf/<record_id>")
    def export_pdf(template_id: str, record_id: str) -> Response:
        pdf = designer.export_pdf(template_id, record_id)
        return Response(
            pdf,
            mimetype="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{template_id}-{record_id}.pdf"',
            },
        )

    @blueprint.errorhandler(FileNotFoundError)
    def not_found(exc: FileNotFoundError) -> tuple[Response, int]:
        return jsonify({"error": str(exc)}), 404

    @blueprint.errorhandler(ValueError)
    def bad_value(exc: ValueError) -> tuple[Response, int]:
        return jsonify({"error": str(exc)}), 400

    @blueprint.errorhandler(SlimReportError)
    def slim_report_error(exc: SlimReportError) -> tuple[Response, int]:
        return jsonify({"error": str(exc)}), _status_for_core_error(exc)

    return blueprint


def _status_for_core_error(exc: SlimReportError) -> int:
    if isinstance(exc, ExporterError):
        return 500
    return 400


def load_report_from_payload(payload: Any) -> Report:
    """Validate and normalize a template payload into a report."""
    if not isinstance(payload, dict):
        raise ValueError("Template payload must be a JSON object.")
    return JSONSerializer().load_mapping(payload)


def request_template_payload() -> dict[str, Any]:
    """Return a report template payload from the current JSON request."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ValueError("Template payload must be a JSON object.")
    if isinstance(payload.get("template"), dict):
        return payload["template"]
    return payload


def request_template_data() -> dict[str, Any]:
    """Return optional render data from the current JSON request."""
    payload = request.get_json(silent=True)
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return payload["data"]
    return {}


def normalize_template_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize designer JSON into the core serializer shape."""
    normalized = dict(payload)
    metadata = dict(normalized.get("metadata") or {})
    if "title" not in metadata and metadata.get("name"):
        metadata["title"] = metadata["name"]
    if "name" not in metadata and metadata.get("title"):
        metadata["name"] = metadata["title"]
    normalized["metadata"] = metadata
    normalized.setdefault("version", "0.1")
    normalized.setdefault("page", {"size": "A4", "orientation": "portrait"})
    normalized.setdefault("objects", [])
    normalized.setdefault("bands", [])
    normalized.setdefault("assets", [])
    return normalized


def _static_response(asset_path: str) -> Response:
    if ".." in asset_path.replace("\\", "/").split("/"):
        raise ValueError("Invalid designer asset path.")
    resource = static_file(asset_path)
    if not resource.is_file():
        raise FileNotFoundError(f"Designer asset not found: {asset_path}.")
    mimetype = mimetypes.guess_type(asset_path)[0] or "application/octet-stream"
    return Response(resource.read_bytes(), mimetype=mimetype)
