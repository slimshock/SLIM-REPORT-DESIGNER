"""Flask blueprint routes for Slim Report Designer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from flask import Blueprint, Response, jsonify, request, url_for

from slim_report_core import ExporterError, Report, SlimReportError, create_default_template

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
        editable_template = template_for_designer(report.to_dict())
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

    @blueprint.post("/templates/<template_id>/designer/save")
    def save_designer_template(template_id: str) -> tuple[Response, int]:
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "Template payload must be a JSON object."}), 400

        record = designer.save_template(template_id, payload)
        return jsonify({"status": "saved", "template": record.to_dict()}), 200

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
    return Report.load_from_dict(payload)
