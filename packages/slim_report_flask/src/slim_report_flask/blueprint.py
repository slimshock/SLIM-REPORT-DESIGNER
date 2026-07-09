"""Flask blueprint routes for Slim Report Designer."""

from __future__ import annotations

import json
import mimetypes
import re
from html import escape
from typing import TYPE_CHECKING, Any

from flask import Blueprint, Response, current_app, jsonify, request, url_for

from slim_report_core import (
    ExporterError,
    Report,
    SlimReportError,
    create_default_template,
    normalize_template,
)
from slim_report_core.assets import (
    AssetError,
    AssetIdError,
    AssetNotFoundError,
    AssetPermissionError,
    AssetStorageError,
    AssetTypeError,
)
from slim_report_core.rendering.context import (
    RenderContext,
    create_render_context,
    get_array_by_path,
)
from slim_report_core.rendering.pagination import pagination_summary
from slim_report_core.serialization import JSONSerializer
from slim_report_core.storage import (
    TemplateIdError,
    TemplateNotFoundError,
    TemplatePermissionError,
    TemplateStorageError,
    TemplateValidationError,
)
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
        blocked = require_access(designer, "view", api=True)
        if blocked:
            return blocked
        return jsonify({"templates": [item.to_dict() for item in designer.list_templates()]})

    @blueprint.route("/templates/new", methods=["GET", "POST"])
    def new_template() -> tuple[Response, int] | Response:
        blocked = require_access(designer, "edit", api=True)
        if blocked:
            return blocked
        if request.method == "GET":
            return jsonify(create_default_template().to_dict())

        payload = request.get_json(silent=True)
        if payload is not None and not isinstance(payload, dict):
            return jsonify({"error": "Template payload must be a JSON object."}), 400

        record = designer.create_template(payload)
        return jsonify({"template": record.to_dict()}), 201

    @blueprint.get("/templates/<template_id>/designer")
    def designer_template(template_id: str) -> Response:
        blocked = require_access(designer, "view", template_id, api=False)
        if blocked:
            return blocked
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
        template_id = request.args.get("template", "")
        blocked = require_access(designer, "view", template_id or None, api=False)
        if blocked:
            return blocked
        html = static_file("index.html").read_text(encoding="utf-8")
        asset_base = url_for(
            "slim_report_designer.designer_ui_asset",
            asset_path="index.html",
        ).rsplit("/", 1)[0]
        api_base = url_for("slim_report_designer.api_templates_root").rsplit(
            "/templates",
            1,
        )[0]
        runtime_config = {
            "apiBase": api_base,
            "templateId": template_id,
            "canSave": designer.can_edit(template_id) if template_id else designer.save_enabled,
            "saveEnabled": designer.save_enabled,
            **designer.csrf_config(),
        }
        config = (
            f'<base href="{asset_base}/">\n'
            "<script>\n"
            f"window.SLIM_REPORT_CONFIG = {json.dumps(runtime_config)};\n"
            f"window.SLIM_REPORT_API_BASE = {json.dumps(api_base)};\n"
            f"window.SLIM_REPORT_TEMPLATE_ID = {json.dumps(template_id)};\n"
            "</script>"
        )
        html = html.replace("<head>\n", f"<head>\n{config}\n", 1)
        return Response(html, mimetype="text/html")

    @blueprint.get("/designer-ui/<path:asset_path>")
    def designer_ui_asset(asset_path: str) -> Response:
        return _static_response(asset_path)

    @blueprint.post("/templates/<template_id>/designer/save")
    def save_designer_template(template_id: str) -> tuple[Response, int]:
        blocked = require_access(designer, "edit", template_id, api=True)
        if blocked:
            return blocked
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "Template payload must be a JSON object."}), 400

        record = designer.save_template(template_id, payload)
        return jsonify({"status": "saved", "template": record.to_dict()}), 200

    @blueprint.get("/api/templates")
    def api_templates_root() -> Response:
        blocked = require_access(designer, "view", api=True)
        if blocked:
            return blocked
        return jsonify({"templates": designer.list_template_summaries()})

    @blueprint.get("/api/templates/<template_id>")
    def api_template(template_id: str) -> Response:
        blocked = require_access(designer, "view", template_id, api=True)
        if blocked:
            return blocked
        template = designer.get_template(template_id)
        return jsonify(template_response(template_id, template))

    @blueprint.get("/api/assets")
    def api_assets() -> Response:
        blocked = require_asset_access(designer, "view", "", api=True)
        if blocked:
            return blocked
        if designer.asset_provider is None:
            return jsonify({"ok": True, "assets": []})
        try:
            return jsonify({"ok": True, "assets": designer.asset_provider.list_assets()})
        except AssetError as exc:
            return asset_error_response(exc)

    @blueprint.get("/api/assets/<asset_id>")
    def api_asset(asset_id: str) -> Response | tuple[Response, int]:
        blocked = require_asset_access(designer, "view", asset_id, api=True)
        if blocked:
            return blocked
        if designer.asset_provider is None:
            return asset_error_response(AssetNotFoundError(f"Asset not found: {asset_id}"))
        try:
            return jsonify({"ok": True, "asset": designer.asset_provider.get_asset(asset_id)})
        except AssetError as exc:
            return asset_error_response(exc)

    @blueprint.post("/api/assets/<asset_id>")
    def save_api_asset(asset_id: str) -> Response | tuple[Response, int]:
        blocked = require_asset_access(designer, "edit", asset_id, api=True)
        if blocked:
            return blocked
        if designer.asset_provider is None:
            return asset_error_response(AssetPermissionError("Asset provider is not configured."))
        try:
            content, content_type, metadata = request_asset_content()
            asset = designer.asset_provider.save_asset(
                asset_id,
                content,
                content_type=content_type,
                metadata=metadata,
            )
            return jsonify({"ok": True, "asset": asset}), 201
        except AssetError as exc:
            return asset_error_response(exc)

    @blueprint.delete("/api/assets/<asset_id>")
    def delete_api_asset(asset_id: str) -> Response | tuple[Response, int]:
        blocked = require_asset_access(designer, "edit", asset_id, api=True)
        if blocked:
            return blocked
        if designer.asset_provider is None:
            return asset_error_response(AssetPermissionError("Asset provider is not configured."))
        try:
            deleted = designer.asset_provider.delete_asset(asset_id)
            return jsonify({"ok": True, "deleted": deleted})
        except AssetError as exc:
            return asset_error_response(exc)

    @blueprint.get("/assets/<asset_id>")
    def serve_asset(asset_id: str) -> Response | tuple[Response, int]:
        blocked = require_asset_access(designer, "view", asset_id, api=False)
        if blocked:
            return blocked
        if designer.asset_provider is None:
            return asset_error_response(AssetNotFoundError(f"Asset not found: {asset_id}"))
        try:
            metadata = designer.asset_provider.get_asset(asset_id)
            with designer.asset_provider.open_asset(asset_id) as asset_file:
                content = asset_file.read()
            mimetype = metadata.get("content_type") or "application/octet-stream"
            response = Response(content, mimetype=str(mimetype))
            if current_app.debug:
                response.headers["Cache-Control"] = "no-store"
            return response
        except AssetError as exc:
            return asset_error_response(exc)

    @blueprint.post("/api/templates/<template_id>")
    def save_api_template(template_id: str) -> tuple[Response, int]:
        blocked = require_access(designer, "edit", template_id, api=True)
        if blocked:
            return blocked
        payload = request_template_payload()
        saved = designer.save_template_mapping(template_id, normalize_template_payload(payload))
        return jsonify(template_response(template_id, saved, ok=True)), 200

    @blueprint.post("/api/preview")
    def api_preview() -> Response:
        try:
            request_payload = request.get_json(silent=True)
            payload = request_template_payload(request_payload)
            template_id = request_template_id(request_payload, payload)
            blocked = require_access(designer, "view", template_id or None, api=True)
            if blocked:
                return blocked
            report = load_report_from_payload(normalize_template_payload(payload))
            data = request_template_data(request_payload, payload, designer, report)
            context = validate_api_report(report)
            return Response(
                render_report_html(report, data, designer),
                mimetype="text/html",
                headers=render_debug_headers(context, data, renderer="html"),
            )
        except Exception as exc:
            return render_failure_response(exc)

    @blueprint.post("/api/export/pdf")
    def api_export_pdf() -> Response:
        try:
            request_payload = request.get_json(silent=True)
            payload = request_template_payload(request_payload)
            template_id = request_template_id(request_payload, payload)
            blocked = require_access(designer, "export", template_id or None, api=True)
            if blocked:
                return blocked
            report = load_report_from_payload(normalize_template_payload(payload))
            data = request_template_data(request_payload, payload, designer, report)
            context = validate_api_report(report)
            return Response(
                render_report_pdf(report, data, designer),
                mimetype="application/pdf",
                headers={
                    "Content-Disposition": content_disposition(default_export_filename(report)),
                    **render_debug_headers(context, data, renderer="pdf"),
                },
            )
        except Exception as exc:
            return render_failure_response(exc)

    @blueprint.get("/print/<template_id>")
    def print_template(template_id: str) -> Response:
        try:
            blocked = require_access(designer, "view", template_id, api=wants_json_response())
            if blocked:
                return blocked
            report = designer.get_report(template_id)
            data = designer.resolve_data(
                template_id,
                request_args=request.args,
                request_json=None,
                report=report,
            )
            context = create_render_context(report, asset_provider=designer.asset_provider)
            html = printable_preview_html(render_report_html(report, data, designer))
            return Response(
                html,
                mimetype="text/html",
                headers=render_debug_headers(context, data, renderer="html"),
            )
        except Exception as exc:
            return render_route_failure_response(exc)

    @blueprint.get("/export/pdf/<template_id>")
    def export_template_pdf(template_id: str) -> Response:
        try:
            blocked = require_access(designer, "export", template_id, api=wants_json_response())
            if blocked:
                return blocked
            report = designer.get_report(template_id)
            data = designer.resolve_data(
                template_id,
                request_args=request.args,
                request_json=None,
                report=report,
            )
            context = create_render_context(report, asset_provider=designer.asset_provider)
            filename = designer.export_filename(template_id, data, request.args, report)
            disposition = "attachment" if truthy_query_arg("download") else "inline"
            return Response(
                render_report_pdf(report, data, designer),
                mimetype="application/pdf",
                headers={
                    "Content-Disposition": content_disposition(filename, disposition=disposition),
                    **render_debug_headers(context, data, renderer="pdf"),
                },
            )
        except Exception as exc:
            return render_route_failure_response(exc)

    @blueprint.get("/templates/<template_id>/preview/<record_id>")
    def preview(template_id: str, record_id: str) -> Response:
        try:
            blocked = require_access(designer, "view", template_id, api=True)
            if blocked:
                return blocked
            report = designer.get_report(template_id)
            data = designer.resolve_data(
                template_id,
                record_id,
                request_args=request.args,
                report=report,
            )
            context = create_render_context(report, asset_provider=designer.asset_provider)
            return Response(
                render_report_html(report, data, designer),
                mimetype="text/html",
                headers=render_debug_headers(context, data, renderer="html"),
            )
        except Exception as exc:
            return render_failure_response(exc)

    @blueprint.get("/templates/<template_id>/export/pdf/<record_id>")
    def export_pdf(template_id: str, record_id: str) -> Response:
        try:
            blocked = require_access(designer, "export", template_id, api=True)
            if blocked:
                return blocked
            report = designer.get_report(template_id)
            data = designer.resolve_data(
                template_id,
                record_id,
                request_args=request.args,
                report=report,
            )
            context = create_render_context(report, asset_provider=designer.asset_provider)
            pdf = designer.export_pdf(template_id, record_id)
            return Response(
                pdf,
                mimetype="application/pdf",
                headers={
                    "Content-Disposition": content_disposition(
                        default_export_filename(report, f"{template_id}-{record_id}")
                    ),
                    **render_debug_headers(context, data, renderer="pdf"),
                },
            )
        except Exception as exc:
            return render_failure_response(exc)

    @blueprint.errorhandler(FileNotFoundError)
    def not_found(exc: FileNotFoundError) -> tuple[Response, int]:
        return error_response("template_not_found", str(exc), 404)

    @blueprint.errorhandler(ValueError)
    def bad_value(exc: ValueError) -> tuple[Response, int]:
        return error_response("invalid_request", str(exc), 400)

    @blueprint.errorhandler(SlimReportError)
    def slim_report_error(exc: SlimReportError) -> tuple[Response, int]:
        return error_response("slim_report_error", str(exc), _status_for_core_error(exc))

    @blueprint.errorhandler(TemplateStorageError)
    def template_storage_error(exc: TemplateStorageError) -> tuple[Response, int]:
        return error_response(_error_code_for_exception(exc), str(exc), _status_for_exception(exc))

    @blueprint.errorhandler(AssetError)
    def asset_error(exc: AssetError) -> tuple[Response, int]:
        return asset_error_response(exc)

    return blueprint


def _status_for_core_error(exc: SlimReportError) -> int:
    if isinstance(exc, ExporterError):
        return 500
    return 400


def render_report_html(report: Report, data: dict[str, Any], designer: SlimReportDesigner) -> str:
    if designer.asset_provider is None:
        return report.render_html(data)
    return report.render_html(data, asset_provider=designer.asset_provider)


def render_report_pdf(report: Report, data: dict[str, Any], designer: SlimReportDesigner) -> bytes:
    if designer.asset_provider is None:
        return report.render_pdf(data)
    return report.render_pdf(data, asset_provider=designer.asset_provider)


def render_failure_response(exc: Exception) -> tuple[Response, int]:
    """Return a JSON preview/export error and log the stack trace."""
    current_app.logger.exception("Slim report preview/export failed")
    status = _status_for_exception(exc)
    return error_response(_error_code_for_exception(exc), str(exc), status, type(exc).__name__)


def render_route_failure_response(exc: Exception) -> tuple[Response, int] | Response:
    """Return JSON or readable browser errors for GET preview/export routes."""
    current_app.logger.exception("Slim report route render/export failed")
    status = _status_for_exception(exc)
    code = _error_code_for_exception(exc)
    message = str(exc)
    if wants_json_response():
        return error_response(code, message, status, type(exc).__name__)
    html = (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<title>Report Error</title>"
        "<style>body{font-family:Arial,sans-serif;margin:32px;color:#111827;}"
        "code{background:#f1f5f9;padding:2px 4px;border-radius:3px;}</style>"
        "</head><body>"
        f"<h1>Report export failed</h1><p>{escape(message)}</p><p><code>{escape(code)}</code></p>"
        "</body></html>"
    )
    return Response(html, status=status, mimetype="text/html")


def error_response(
    code: str,
    message: str,
    status: int,
    exc_type: str | None = None,
) -> tuple[Response, int]:
    payload: dict[str, Any] = {
        "ok": False,
        "error": message,
        "error_detail": {
            "code": code,
            "message": message,
        },
    }
    if exc_type:
        payload["type"] = exc_type
    return jsonify(payload), status


def _error_code_for_exception(exc: Exception) -> str:
    if isinstance(exc, AssetError):
        return _asset_error_code(exc)
    if isinstance(exc, FileNotFoundError):
        return "template_not_found"
    if isinstance(exc, TemplateNotFoundError):
        return "template_not_found"
    if isinstance(exc, TemplateIdError):
        return "invalid_template_id"
    if isinstance(exc, TemplateValidationError):
        return "invalid_template"
    if isinstance(exc, PermissionError):
        return "forbidden"
    if isinstance(exc, TemplatePermissionError):
        return "forbidden"
    if isinstance(exc, ValueError):
        return "invalid_request"
    if isinstance(exc, SlimReportError):
        return "slim_report_error"
    if isinstance(exc, TemplateStorageError):
        return "template_storage_error"
    return "server_error"


def _status_for_exception(exc: Exception) -> int:
    if isinstance(exc, AssetError):
        return _status_for_asset_exception(exc)
    if isinstance(exc, FileNotFoundError):
        return 404
    if isinstance(exc, TemplateNotFoundError):
        return 404
    if isinstance(exc, PermissionError):
        return 403
    if isinstance(exc, TemplatePermissionError):
        return 403
    if isinstance(exc, TemplateValidationError):
        return 400
    if isinstance(exc, ValueError):
        return 400
    if isinstance(exc, SlimReportError):
        return _status_for_core_error(exc)
    return 500


def _asset_error_code(exc: AssetError) -> str:
    if isinstance(exc, AssetNotFoundError):
        return "asset_not_found"
    if isinstance(exc, AssetIdError):
        return "invalid_asset_id"
    if isinstance(exc, AssetPermissionError):
        return "asset_forbidden"
    if isinstance(exc, AssetTypeError):
        return "unsupported_asset_type"
    if isinstance(exc, AssetStorageError):
        return "asset_storage_error"
    return "asset_error"


def _status_for_asset_exception(exc: AssetError) -> int:
    if isinstance(exc, AssetNotFoundError):
        return 404
    if isinstance(exc, AssetIdError):
        return 400
    if isinstance(exc, AssetPermissionError):
        return 403
    if isinstance(exc, AssetTypeError):
        return 400
    if isinstance(exc, AssetStorageError):
        return 400
    return 500


def asset_error_response(exc: AssetError) -> tuple[Response, int]:
    code = _asset_error_code(exc)
    return (
        jsonify(
            {
                "ok": False,
                "error": {
                    "code": code,
                    "message": str(exc),
                },
            }
        ),
        _status_for_asset_exception(exc),
    )


def require_access(
    designer: SlimReportDesigner,
    action: str,
    template_id: str | None = None,
    *,
    api: bool,
) -> Response | tuple[Response, int] | None:
    if not designer.is_authenticated():
        if api:
            return error_response("unauthorized", "Authentication required.", 401)
        return Response("Authentication required.", status=401, mimetype="text/plain")
    if template_id:
        allowed = {
            "view": designer.can_view,
            "edit": designer.can_edit,
            "export": designer.can_export,
        }[action](template_id)
        if not allowed:
            if api:
                return error_response("forbidden", "Permission denied.", 403)
            return Response("Permission denied.", status=403, mimetype="text/plain")
    return None


def require_asset_access(
    designer: SlimReportDesigner,
    action: str,
    asset_id: str,
    *,
    api: bool,
) -> Response | tuple[Response, int] | None:
    if not designer.is_authenticated():
        if api:
            return asset_error_response(AssetPermissionError("Authentication required."))
        return Response("Authentication required.", status=401, mimetype="text/plain")
    if asset_id:
        allowed = (
            designer.can_view_asset(asset_id)
            if action == "view"
            else designer.can_edit_asset(asset_id)
        )
        if not allowed:
            if api:
                return asset_error_response(AssetPermissionError("Permission denied."))
            return Response("Permission denied.", status=403, mimetype="text/plain")
    return None


def request_asset_content() -> tuple[bytes, str | None, dict[str, Any]]:
    if request.files:
        upload = next(iter(request.files.values()))
        content = upload.read()
        return content, upload.mimetype, {"filename": upload.filename}
    content = request.get_data() or b""
    content_type = request.headers.get("Content-Type")
    return content, content_type, {}


def template_response(
    template_id: str,
    template: dict[str, Any],
    *,
    ok: bool | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "template_id": template_id,
        "template": template,
    }
    if ok is not None:
        payload["ok"] = ok
    payload.update(template)
    return payload


def load_report_from_payload(payload: Any) -> Report:
    """Validate and normalize a template payload into a report."""
    if not isinstance(payload, dict):
        raise ValueError("Template payload must be a JSON object.")
    return JSONSerializer().load_mapping(payload)


def validate_api_report(report: Report) -> RenderContext:
    """Validate a designer API report before preview/export rendering."""
    context = create_render_context(report)
    if not context.objects:
        raise ValueError("Template must contain at least one object for preview or export.")
    if context.page.width_px <= 0 or context.page.height_px <= 0:
        raise ValueError("Template page width and height must be positive.")
    return context


def render_debug_headers(
    context: RenderContext,
    data: Any | None = None,
    *,
    renderer: str = "html",
) -> dict[str, str]:
    """Return lightweight debug headers for preview/export fidelity checks."""
    repeat = next(
        (
            band.repeat
            for band in context.bands
            if band.id == "detail" and band.repeat.get("enabled") and band.repeat.get("data_path")
        ),
        {},
    )
    repeat_data_path = str(repeat.get("data_path", ""))
    repeat_rows = get_array_by_path(data or {}, repeat_data_path) if repeat_data_path else []
    summary = pagination_summary(context, data)
    return {
        "X-Slim-Report-Page-Count": str(summary.page_count),
        "X-Slim-Report-Template-Name": context.title,
        "X-Slim-Report-Renderer": renderer,
        "X-Slim-Report-Object-Count": str(len(context.objects)),
        "X-Slim-Report-Page-Unit": context.page.unit,
        "X-Slim-Report-Page-Width": str(context.page.width_px),
        "X-Slim-Report-Page-Height": str(context.page.height_px),
        "X-Slim-Report-Has-Data-Sample": (
            "true" if isinstance(data, dict) and bool(data) else "false"
        ),
        "X-Slim-Report-Repeat-Data-Path": repeat_data_path,
        "X-Slim-Report-Repeat-Row-Count": str(len(repeat_rows)),
        "X-Slim-Report-Repeated-Row-Count": str(summary.repeated_row_count),
        "X-Slim-Report-Table-Row-Count": str(summary.table_row_count),
    }


def print_settings_for_report(report: Report) -> dict[str, Any]:
    """Return export settings with defaults applied."""
    settings = dict(getattr(getattr(report, "page", None), "print", {}) or {})
    title = str(getattr(report.metadata, "title", "") or "").strip()
    settings.setdefault("show_browser_print_button", True)
    settings.setdefault("default_filename", safe_pdf_filename(title or "report"))
    settings.setdefault("pdf_title", title or "Untitled Report")
    settings.setdefault("pdf_author", "Slim Report Designer")
    settings.setdefault("print_background", True)
    return settings


def default_export_filename(report: Report, fallback: str = "report") -> str:
    settings = print_settings_for_report(report)
    return safe_pdf_filename(settings.get("default_filename") or fallback)


def safe_pdf_filename(value: Any, fallback: str = "report.pdf") -> str:
    """Return a Windows-safe PDF filename from arbitrary title text."""
    raw = str(value or "").strip()
    if raw.lower().endswith(".pdf"):
        raw = raw[:-4]
    slug = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', " ", raw)
    slug = re.sub(r"[^A-Za-z0-9._ -]+", " ", slug)
    slug = re.sub(r"[\s_-]+", "-", slug).strip(" .-_")
    reserved = {
        "con",
        "prn",
        "aux",
        "nul",
        *(f"com{index}" for index in range(1, 10)),
        *(f"lpt{index}" for index in range(1, 10)),
    }
    if not slug or slug.lower() in reserved:
        fallback_slug = str(fallback or "report.pdf").removesuffix(".pdf")
        slug = re.sub(r"[^A-Za-z0-9._-]+", "-", fallback_slug).strip(" .-_") or "report"
    return f"{slug[:120]}.pdf"


def content_disposition(filename: str, *, disposition: str = "attachment") -> str:
    resolved = "attachment" if disposition == "attachment" else "inline"
    return f'{resolved}; filename="{safe_pdf_filename(filename)}"'


def printable_preview_html(html: str) -> str:
    """Return full report HTML adjusted for direct browser printing."""
    printable_css = (
        "<style id=\"slim-report-print-route-css\">"
        "html,body{background:#fff!important;}"
        ".slim-report-preview-toolbar,.slim-report-print-button{display:none!important;}"
        ".slim-report-preview{padding:0!important;background:#fff!important;}"
        ".slim-report-page{box-shadow:none!important;margin:0 auto!important;}"
        "@media print{body{margin:0!important;background:#fff!important;}"
        ".slim-report-page{margin:0!important;box-shadow:none!important;}}"
        "</style>"
    )
    html = re.sub(
        r'<div class="slim-report-preview-toolbar">.*?</div>',
        "",
        html,
        flags=re.DOTALL,
    )
    if "</head>" in html:
        html = html.replace("</head>", f"{printable_css}</head>", 1)
    else:
        html = f"{printable_css}{html}"
    if truthy_query_arg("auto_print"):
        script = (
            "<script>window.addEventListener('load',function(){window.print();});</script>"
        )
        html = (
            html.replace("</body>", f"{script}</body>", 1)
            if "</body>" in html
            else html + script
        )
    return html


def wants_json_response() -> bool:
    best = request.accept_mimetypes.best_match(["application/json", "text/html"])
    return best == "application/json" and (
        request.accept_mimetypes["application/json"] >= request.accept_mimetypes["text/html"]
    )


def truthy_query_arg(name: str) -> bool:
    return str(request.args.get(name, "")).strip().lower() in {"1", "true", "yes", "on"}


def request_template_payload(payload: Any | None = None) -> dict[str, Any]:
    """Return a report template payload from the current JSON request."""
    if payload is None:
        payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ValueError("Template payload must be a JSON object.")
    if _looks_like_template(payload):
        return payload
    if isinstance(payload.get("template"), dict):
        return payload["template"]
    return payload


def request_template_data(
    payload: Any | None = None,
    template: dict[str, Any] | None = None,
    designer: SlimReportDesigner | None = None,
    report: Report | None = None,
) -> dict[str, Any]:
    """Return optional render data from the current JSON request."""
    if payload is None:
        payload = request.get_json(silent=True)
    if isinstance(payload, dict) and isinstance(payload.get("template"), dict):
        if isinstance(payload.get("data"), dict):
            return payload["data"]
    elif (
        isinstance(payload, dict)
        and isinstance(payload.get("data"), dict)
        and not _looks_like_template(payload)
    ):
        return payload["data"]
    template_id = request_template_id(payload, template)
    if designer is not None and template_id:
        try:
            resolved = designer.resolve_data(
                str(template_id),
                "sample",
                request_args=request.args,
                request_json=payload,
                report=report,
            )
        except Exception:
            raise
        if isinstance(resolved, dict):
            return resolved
    data_metadata = template.get("data") if isinstance(template, dict) else None
    if isinstance(data_metadata, dict) and isinstance(data_metadata.get("sample"), dict):
        return data_metadata["sample"]
    return {}


def _looks_like_template(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and isinstance(value.get("metadata"), dict)
        and isinstance(value.get("page"), dict)
        and isinstance(value.get("objects"), list)
        and isinstance(value.get("bands"), list)
    )


def request_template_id(payload: Any | None, template: dict[str, Any] | None = None) -> str:
    if isinstance(payload, dict) and payload.get("template_id"):
        return str(payload["template_id"])
    metadata = template.get("metadata") if isinstance(template, dict) else None
    if isinstance(metadata, dict):
        custom = metadata.get("custom")
        if isinstance(custom, dict) and custom.get("id"):
            return str(custom["id"])
        if metadata.get("template_id"):
            return str(metadata["template_id"])
    return ""


def normalize_template_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize designer JSON into the core serializer shape."""
    return normalize_template(payload)


def _static_response(asset_path: str) -> Response:
    if ".." in asset_path.replace("\\", "/").split("/"):
        raise ValueError("Invalid designer asset path.")
    resource = static_file(asset_path)
    if not resource.is_file():
        raise FileNotFoundError(f"Designer asset not found: {asset_path}.")
    mimetype = mimetypes.guess_type(asset_path)[0] or "application/octet-stream"
    response = Response(resource.read_bytes(), mimetype=mimetype)
    if current_app.debug:
        response.headers["Cache-Control"] = "no-store"
    return response
