"""Flask blueprint routes for Slim Report Designer."""

from __future__ import annotations

import copy
import json
import mimetypes
import re
from html import escape
from typing import TYPE_CHECKING, Any

from flask import Blueprint, Response, current_app, jsonify, request, url_for

from slim_report_core import (
    ConnectionTestResult,
    ConnectionTimeoutError,
    CreateMySQLDataSourceCommand,
    CreateQueryDatasetCommand,
    CreateViewDatasetCommand,
    CredentialUnavailableError,
    DatabaseUnavailableError,
    DatabaseViewSchema,
    DatasetConfigurationResult,
    DatasetExecutionCancellationToken,
    DatasetFreshnessService,
    DatasetInUseError,
    DatasetNotFoundError,
    DatasetSummary,
    DataSourceInUseError,
    DataSourceNotFoundError,
    DataSourceSummary,
    ExporterError,
    MetadataAccessDeniedError,
    MissingDriverError,
    NewReportConfiguration,
    NewReportDataConfiguration,
    NewReportLayoutConfiguration,
    NewReportPageConfiguration,
    NewReportWizardBuilder,
    QueryExecutionTimeoutError,
    QueryFieldDiscoveryResult,
    QueryParameter,
    Report,
    ReportDataset,
    ReportDataSource,
    ReportPreviewReadinessService,
    ReportRuntimeParameterService,
    ReportSaveValidationService,
    ReportTemplateReopenService,
    RuntimeParameterDatasetError,
    RuntimePreviewOptions,
    SelectedReportField,
    SlimReportError,
    UpdateMySQLDataSourceCommand,
    ViewNotFoundError,
    create_default_template,
    credential_resolution_status,
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
    TemplateNotFoundError,
    TemplateStorageError,
)
from slim_report_designer_ui import static_file

from .designer import render_designer_page, template_for_designer
from .errors import map_safe_error

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

        config_parts = [
            f'<base href="{escape(asset_base, quote=True)}/">',
            (
                '<meta name="slim-report-api-base" '
                f'content="{escape(str(runtime_config["apiBase"]), quote=True)}">'
            ),
            (
                '<meta name="slim-report-template-id" '
                f'content="{escape(str(runtime_config["templateId"]), quote=True)}">'
            ),
            (
                '<meta name="slim-report-can-save" '
                f'content="{str(bool(runtime_config["canSave"])).lower()}">'
            ),
            (
                '<meta name="slim-report-save-enabled" '
                f'content="{str(bool(runtime_config["saveEnabled"])).lower()}">'
            ),
        ]

        csrf_header_name = runtime_config.get("csrfHeaderName")
        csrf_token = runtime_config.get("csrfToken")

        if csrf_header_name:
            config_parts.append(
                '<meta name="slim-report-csrf-header" '
                f'content="{escape(str(csrf_header_name), quote=True)}">'
            )

        if csrf_token:
            config_parts.append(
                '<meta name="slim-report-csrf-token" '
                f'content="{escape(str(csrf_token), quote=True)}">'
            )

        config = "\n".join(config_parts)
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
        report = designer.serializer.load_mapping(designer.get_template(template_id))
        template = designer.serializer.dump_mapping(report)
        return jsonify(template_response(template_id, template))

    @blueprint.get("/api/designer/data-sources")
    def list_saved_data_sources() -> Response:
        template_id = str(request.args.get("template") or "")
        blocked = require_access(designer, "view", template_id or None, api=True)
        if blocked:
            return blocked
        if not template_id:
            raise ValueError("A template id is required.")
        report = designer.get_report(template_id)
        return jsonify(_data_source_list_payload(designer, report))

    @blueprint.post("/api/designer/reopen/inspect")
    def inspect_reopened_report() -> Response:
        payload, template_id, report = _data_source_request(designer)
        del payload
        blocked = require_access(designer, "view", template_id or None, api=True)
        if blocked:
            return blocked
        service = ReportTemplateReopenService(credential_resolver=designer.credential_resolver)
        return _no_store(jsonify(service.inspect(report).to_dict()))

    @blueprint.post("/api/designer/preview/readiness")
    def inspect_preview_readiness() -> Response:
        payload, template_id, report = _data_source_request(designer)
        blocked = require_access(designer, "view", template_id or None, api=True)
        if blocked:
            return blocked
        reopen = ReportTemplateReopenService(credential_resolver=designer.credential_resolver)
        result = ReportPreviewReadinessService(reopen).evaluate(
            report,
            dataset_id=_optional_text(payload.get("datasetId")),
        )
        return _no_store(jsonify(result.to_dict()))

    @blueprint.post("/api/designer/save/validate")
    def validate_designer_save() -> Response:
        _payload, template_id, report = _data_source_request(designer)
        blocked = require_access(designer, "edit", template_id or None, api=True)
        if blocked:
            return blocked
        reopen = ReportTemplateReopenService(credential_resolver=designer.credential_resolver)
        result = ReportSaveValidationService(reopen).evaluate(report)
        return _no_store(jsonify(result.to_dict()))

    @blueprint.post("/api/designer/credentials/clear")
    def clear_runtime_credentials() -> Response:
        payload = _json_object_request()
        template_id = str(payload.get("template_id") or "")
        blocked = require_access(designer, "edit", template_id or None, api=True)
        if blocked:
            return blocked
        report_key = _runtime_report_key(payload)
        source_id = _optional_text(payload.get("dataSourceId"))
        if source_id is None:
            designer.runtime_credential_store.clear_report(report_key)
        else:
            designer.runtime_credential_store.clear_password(report_key, source_id)
        return _no_store(jsonify({"ok": True}))

    @blueprint.post("/api/designer/data-sources/list")
    def list_active_data_sources() -> Response:
        payload, template_id, report = _data_source_request(designer)
        del payload
        blocked = require_access(designer, "view", template_id or None, api=True)
        if blocked:
            return blocked
        return jsonify(_data_source_list_payload(designer, report))

    @blueprint.post("/api/designer/data-sources/mysql")
    def create_mysql_data_source() -> tuple[Response, int] | Response:
        payload, template_id, report = _data_source_request(designer)
        blocked = require_access(designer, "edit", template_id or None, api=True)
        if blocked:
            return blocked
        service = designer.data_source_management_service
        source = service.create_mysql_data_source(report, _create_mysql_command(payload))
        _store_source_runtime_password(designer, payload, source)
        return jsonify(
            _data_source_mutation_payload(
                designer,
                report,
                source.id,
                "MySQL data source created.",
            )
        ), 201

    @blueprint.put("/api/designer/data-sources/<data_source_id>")
    def update_mysql_data_source(data_source_id: str) -> Response:
        payload, template_id, report = _data_source_request(designer)
        blocked = require_access(designer, "edit", template_id or None, api=True)
        if blocked:
            return blocked
        service = designer.data_source_management_service
        if payload.get("credentialMode") in {"passwordRef", "none"}:
            _clear_source_runtime_password(designer, payload, data_source_id)
        source = service.update_mysql_data_source(
            report,
            _update_mysql_command(data_source_id, payload),
        )
        _store_source_runtime_password(designer, payload, source)
        return jsonify(
            _data_source_mutation_payload(
                designer,
                report,
                source.id,
                "MySQL data source updated.",
            )
        )

    @blueprint.delete("/api/designer/data-sources/<data_source_id>")
    def delete_mysql_data_source(data_source_id: str) -> tuple[Response, int] | Response:
        payload, template_id, report = _data_source_request(designer)
        blocked = require_access(designer, "edit", template_id or None, api=True)
        if blocked:
            return blocked
        service = designer.data_source_management_service
        try:
            service.remove_data_source(report, data_source_id, cascade=False)
        except DataSourceInUseError as exc:
            dependents = [
                item.name for item in report.datasets if item.data_source_id == data_source_id
            ]
            return jsonify(
                {
                    "ok": False,
                    "error": str(exc),
                    "error_detail": {
                        "code": "data_source_in_use",
                        "message": str(exc),
                    },
                    "dependents": dependents,
                }
            ), 409
        result = _data_source_mutation_payload(
            designer,
            report,
            None,
            "MySQL data source removed.",
        )
        _clear_source_runtime_password(designer, payload, data_source_id)
        result["deletedId"] = data_source_id
        return jsonify(result)

    @blueprint.post("/api/designer/data-sources/test")
    def test_mysql_configuration() -> Response:
        payload = _json_object_request()
        template_id = str(payload.get("template_id") or "")
        blocked = require_access(designer, "view", template_id or None, api=True)
        if blocked:
            return blocked
        result = designer.data_source_management_service.test_mysql_configuration(
            _create_mysql_command(payload)
        )
        return jsonify(_connection_test_payload(result))

    @blueprint.post("/api/designer/data-sources/<data_source_id>/test")
    def test_saved_mysql_data_source(data_source_id: str) -> Response:
        payload, template_id, report = _data_source_request(designer)
        blocked = require_access(designer, "view", template_id or None, api=True)
        if blocked:
            return blocked
        service = designer.data_source_management_service
        runtime_password = payload.get("runtimePassword")
        if runtime_password is not None:
            report_key = _optional_runtime_report_key(payload)
            if report_key is not None:
                designer.runtime_credential_store.set_password(
                    report_key, data_source_id, str(runtime_password)
                )
            service.update_mysql_data_source(
                report,
                UpdateMySQLDataSourceCommand(
                    data_source_id=data_source_id,
                    runtime_password=str(runtime_password),
                ),
            )
        result = service.test_data_source_connection(report, data_source_id)
        return jsonify(_connection_test_payload(result))

    @blueprint.post("/api/designer/datasets/list")
    def list_active_datasets() -> Response:
        payload, template_id, report = _data_source_request(designer)
        del payload
        blocked = require_access(designer, "view", template_id or None, api=True)
        if blocked:
            return blocked
        return jsonify(_dataset_list_payload(designer, report))

    @blueprint.post("/api/designer/datasets/<dataset_id>/get")
    def get_active_dataset(dataset_id: str) -> Response:
        payload, template_id, report = _data_source_request(designer)
        del payload
        blocked = require_access(designer, "view", template_id or None, api=True)
        if blocked:
            return blocked
        dataset = designer.data_source_management_service.get_dataset(report, dataset_id)
        return jsonify({"ok": True, "dataset": dataset.to_dict()})

    @blueprint.post("/api/designer/data-sources/<data_source_id>/views/list")
    def list_reporting_views(data_source_id: str) -> Response:
        payload, template_id, report = _data_source_request(designer)
        del payload
        blocked = require_access(designer, "view", template_id or None, api=True)
        if blocked:
            return blocked
        views = designer.data_source_management_service.list_available_views(report, data_source_id)
        return jsonify(
            {
                "ok": True,
                "views": [
                    {
                        "schemaName": item.schema_name,
                        "viewName": item.view_name,
                        "displayName": item.display_name or item.view_name,
                    }
                    for item in views
                ],
            }
        )

    @blueprint.post("/api/designer/data-sources/<data_source_id>/views/inspect")
    def inspect_reporting_view(data_source_id: str) -> Response:
        payload, template_id, report = _data_source_request(designer)
        blocked = require_access(designer, "view", template_id or None, api=True)
        if blocked:
            return blocked
        schema = designer.data_source_management_service.inspect_view(
            report,
            data_source_id,
            str(payload.get("viewName") or ""),
        )
        return jsonify(_view_schema_payload(schema))

    @blueprint.post("/api/designer/query/validate")
    def validate_dataset_query_configuration() -> Response:
        payload, template_id, _report = _data_source_request(designer)
        blocked = require_access(designer, "view", template_id or None, api=True)
        if blocked:
            return blocked
        result = designer.data_source_management_service.validate_query_dataset_configuration(
            query=str(payload.get("query") or ""),
            parameters=_query_parameters(payload),
        )
        return jsonify(
            {
                "ok": True,
                "statement": result.root_statement,
                "parameters": list(result.parameters),
                "dialect": result.dialect,
                "warnings": list(result.warnings),
                "maxQueryLength": (
                    designer.data_source_management_service.sql_validator.policy.max_query_length
                ),
            }
        )

    @blueprint.post("/api/designer/query/discover")
    def discover_dataset_query_configuration() -> Response:
        payload, template_id, report = _data_source_request(designer)
        blocked = require_access(designer, "view", template_id or None, api=True)
        if blocked:
            return blocked
        service = designer.data_source_management_service
        source = service.get_data_source(report, str(payload.get("dataSourceId") or ""))
        result = service.discover_query_configuration_fields(
            data_source=source,
            query=str(payload.get("query") or ""),
            parameters=_query_parameters(payload),
            parameter_values=_parameter_values(payload),
        )
        return jsonify(_discovery_payload(result))

    @blueprint.post("/api/designer/datasets/view")
    def create_view_dataset() -> tuple[Response, int] | Response:
        payload, template_id, report = _data_source_request(designer)
        blocked = require_access(designer, "edit", template_id or None, api=True)
        if blocked:
            return blocked
        result = designer.data_source_management_service.create_view_dataset(
            report,
            CreateViewDatasetCommand(
                name=str(payload.get("name") or ""),
                data_source_id=str(payload.get("dataSourceId") or ""),
                view_name=str(payload.get("viewName") or ""),
                dataset_id=_optional_text(payload.get("datasetId")),
                discover_fields=True,
            ),
        )
        return jsonify(
            _dataset_mutation_payload(designer, report, result, "View dataset created.")
        ), 201

    @blueprint.post("/api/designer/datasets/query")
    def create_query_dataset() -> tuple[Response, int] | Response:
        payload, template_id, report = _data_source_request(designer)
        blocked = require_access(designer, "edit", template_id or None, api=True)
        if blocked:
            return blocked
        result = designer.data_source_management_service.create_query_dataset(
            report,
            CreateQueryDatasetCommand(
                name=str(payload.get("name") or ""),
                data_source_id=str(payload.get("dataSourceId") or ""),
                query=str(payload.get("query") or ""),
                parameters=_query_parameters(payload),
                dataset_id=_optional_text(payload.get("datasetId")),
                discover_fields=True,
            ),
            parameter_values=_parameter_values(payload),
        )
        return jsonify(
            _dataset_mutation_payload(designer, report, result, "Query dataset created.")
        ), 201

    @blueprint.post("/api/designer/new-report/build")
    def build_new_report() -> Response:
        payload = _json_object_request()
        template_id = str(payload.get("template_id") or "")
        blocked = require_access(designer, "edit", template_id or None, api=True)
        if blocked:
            return blocked
        configuration = _new_report_configuration(payload.get("configuration"))
        if configuration.data and configuration.data.dataset.source_type.value == "query":
            designer.data_source_management_service.sql_validator.validate_dataset(
                configuration.data.dataset
            )
        report = NewReportWizardBuilder().build(configuration)
        return jsonify(
            {
                "ok": True,
                "message": "New report created.",
                "template": report.template.to_dict(),
            }
        )

    @blueprint.post("/api/designer/datasets/<dataset_id>/runtime-parameters")
    def runtime_parameter_schema(dataset_id: str) -> Response:
        _payload, template_id, report = _data_source_request(designer)
        blocked = require_access(designer, "view", template_id or None, api=True)
        if blocked:
            return blocked
        schema = ReportRuntimeParameterService().schema_for_primary_dataset(report, dataset_id)
        return jsonify(schema.to_dict())

    @blueprint.post("/api/designer/datasets/<dataset_id>/runtime-parameters/validate")
    def validate_runtime_parameters(dataset_id: str) -> tuple[Response, int] | Response:
        payload, template_id, report = _data_source_request(designer)
        blocked = require_access(designer, "view", template_id or None, api=True)
        if blocked:
            return blocked
        values = payload.get("values", {})
        if not isinstance(values, dict):
            raise ValueError("Runtime parameter values must be a JSON object.")
        dataset = report.get_dataset(dataset_id)
        if dataset is None:
            raise RuntimeParameterDatasetError(f"Report dataset '{dataset_id}' was not found.")
        result = ReportRuntimeParameterService().resolver.validate_dataset(dataset, values)
        if not result.valid:
            return jsonify(
                {
                    "valid": False,
                    "datasetId": dataset_id,
                    "errors": [issue.to_dict() for issue in result.issues],
                }
            ), 400
        resolved = result.resolved
        return jsonify(
            {
                "valid": True,
                "datasetId": dataset_id,
                "parameterCount": len(dataset.parameters),
                "usedDefaults": list(resolved.used_defaults if resolved else ()),
            }
        )

    @blueprint.put("/api/designer/datasets/<dataset_id>/view")
    def update_view_dataset(dataset_id: str) -> Response:
        payload, template_id, report = _data_source_request(designer)
        blocked = require_access(designer, "edit", template_id or None, api=True)
        if blocked:
            return blocked
        result = designer.data_source_management_service.update_view_dataset(
            report,
            dataset_id,
            name=_optional_payload_text(payload, "name"),
            view_name=_optional_payload_text(payload, "viewName"),
            refresh_fields=payload.get("refreshFields") is True,
        )
        return jsonify(_dataset_mutation_payload(designer, report, result, "View dataset updated."))

    @blueprint.put("/api/designer/datasets/<dataset_id>/query")
    def update_query_dataset(dataset_id: str) -> Response:
        payload, template_id, report = _data_source_request(designer)
        blocked = require_access(designer, "edit", template_id or None, api=True)
        if blocked:
            return blocked
        service = designer.data_source_management_service
        current = service.get_dataset(report, dataset_id)
        query = _optional_payload_text(payload, "query")
        parameters = _query_parameters(payload) if "parameters" in payload else None
        requires_discovery = (query is not None and query != current.query) or (
            parameters is not None
            and tuple(item.to_dict() for item in parameters)
            != tuple(item.to_dict() for item in current.parameters)
        )
        result = service.update_query_dataset(
            report,
            dataset_id,
            name=_optional_payload_text(payload, "name"),
            query=query,
            parameters=parameters,
        )
        if requires_discovery:
            discovery = service.discover_query_fields(
                report,
                dataset_id,
                parameter_values=_parameter_values(payload),
            )
            result = service.apply_discovered_fields(report, dataset_id, discovery)
        return jsonify(
            _dataset_mutation_payload(designer, report, result, "Query dataset updated.")
        )

    @blueprint.post("/api/designer/datasets/<dataset_id>/refresh-view-fields")
    def refresh_dataset_view_fields(dataset_id: str) -> Response:
        payload, template_id, report = _data_source_request(designer)
        del payload
        blocked = require_access(designer, "edit", template_id or None, api=True)
        if blocked:
            return blocked
        result = designer.data_source_management_service.refresh_view_dataset_fields(
            report, dataset_id
        )
        return jsonify(
            _dataset_mutation_payload(designer, report, result, "View fields refreshed.")
        )

    @blueprint.post("/api/designer/datasets/<dataset_id>/freshness")
    def check_dataset_freshness(dataset_id: str) -> Response:
        payload, template_id, report = _data_source_request(designer)
        blocked = require_access(designer, "view", template_id or None, api=True)
        if blocked:
            return blocked
        service = designer.data_source_management_service
        dataset = service.get_dataset(report, dataset_id)
        if dataset.source_type.value == "view":
            discovery = service.inspect_view_dataset_fields(report, dataset_id)
            fields = discovery.fields
            warnings = discovery.warnings
        else:
            discovery = service.discover_query_fields(
                report,
                dataset_id,
                parameter_values=_parameter_values(payload),
            )
            fields = discovery.fields
            warnings = discovery.warnings
        result = DatasetFreshnessService().compare(
            report,
            dataset_id,
            fields,
            warnings=warnings,
        )
        return _no_store(jsonify(result.to_dict()))

    @blueprint.post("/api/designer/datasets/<dataset_id>/discover-fields")
    def discover_existing_dataset_fields(dataset_id: str) -> Response:
        payload, template_id, report = _data_source_request(designer)
        blocked = require_access(designer, "view", template_id or None, api=True)
        if blocked:
            return blocked
        result = designer.data_source_management_service.discover_query_fields(
            report,
            dataset_id,
            parameter_values=_parameter_values(payload),
        )
        return jsonify(_discovery_payload(result))

    @blueprint.post("/api/designer/datasets/<dataset_id>/apply-fields")
    def apply_existing_dataset_fields(dataset_id: str) -> Response:
        payload, template_id, report = _data_source_request(designer)
        blocked = require_access(designer, "edit", template_id or None, api=True)
        if blocked:
            return blocked
        service = designer.data_source_management_service
        discovery = service.discover_query_fields(
            report,
            dataset_id,
            parameter_values=_parameter_values(payload),
        )
        result = service.apply_discovered_fields(report, dataset_id, discovery)
        return jsonify(
            _dataset_mutation_payload(designer, report, result, "Discovered fields applied.")
        )

    @blueprint.delete("/api/designer/datasets/<dataset_id>")
    def delete_dataset(dataset_id: str) -> Response:
        payload, template_id, report = _data_source_request(designer)
        del payload
        blocked = require_access(designer, "edit", template_id or None, api=True)
        if blocked:
            return blocked
        designer.data_source_management_service.remove_dataset(report, dataset_id)
        result = _dataset_list_payload(designer, report)
        result.update(
            {
                "template": designer.serializer.dump_mapping(report),
                "deletedId": dataset_id,
                "message": "Dataset removed.",
            }
        )
        return jsonify(result)

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

    @blueprint.post("/api/designer/preview/live")
    def api_live_preview() -> tuple[Response, int] | Response:
        request_id = ""
        try:
            request_payload = request.get_json(silent=True)
            if not isinstance(request_payload, dict):
                raise ValueError("Live preview payload must be a JSON object.")
            payload = request_template_payload(request_payload)
            template_id = request_template_id(request_payload, payload)
            blocked = require_access(designer, "view", template_id or None, api=True)
            if blocked:
                return blocked
            report = load_report_from_payload(normalize_template_payload(payload))
            dataset_id = _optional_request_text(request_payload.get("datasetId"))
            report = _authoritative_live_preview_report(
                designer,
                report,
                template_id=template_id,
                dataset_id=dataset_id,
            )
            _inject_runtime_credentials(designer, request_payload, report)
            parameter_values = request_payload.get("parameterValues")
            if parameter_values is not None and not isinstance(parameter_values, dict):
                raise ValueError("parameterValues must be a JSON object.")
            raw_options = request_payload.get("options") or {}
            if not isinstance(raw_options, dict):
                raise ValueError("options must be a JSON object.")
            include_debug_metadata = raw_options.get("includeDebugMetadata", False)
            if not isinstance(include_debug_metadata, bool):
                raise ValueError("includeDebugMetadata must be a boolean.")
            options = RuntimePreviewOptions(
                dataset_id=dataset_id,
                max_rows=raw_options.get("maxRows"),
                timeout_seconds=raw_options.get("timeoutSeconds"),
                include_debug_metadata=include_debug_metadata,
            )
            token = DatasetExecutionCancellationToken()
            request_id = designer.preview_cancellation_registry.register(
                user_key=_preview_user_key(),
                report_key=template_id or "unsaved",
                token=token,
                request_id=_optional_request_text(request_payload.get("requestId")),
            )
            result = designer.runtime_report_render_service.render_html(
                report,
                parameter_values=parameter_values,
                options=options,
                cancellation_token=token,
                asset_provider=designer.asset_provider,
            )
            response = jsonify(
                {
                    "success": True,
                    "requestId": request_id,
                    "html": result.html,
                    "summary": _runtime_preview_summary_payload(result.summary),
                }
            )
            return _no_store(response)
        except Exception as exc:
            return live_preview_failure_response(exc)
        finally:
            if request_id:
                designer.preview_cancellation_registry.remove(request_id)

    @blueprint.post("/api/designer/preview/<request_id>/cancel")
    def api_cancel_live_preview(request_id: str) -> tuple[Response, int] | Response:
        payload = request.get_json(silent=True) or {}
        template_id = payload.get("template_id") if isinstance(payload, dict) else None
        blocked = require_access(designer, "view", template_id or None, api=True)
        if blocked:
            return blocked
        cancelled = designer.preview_cancellation_registry.cancel(
            request_id,
            user_key=_preview_user_key(),
        )
        response = jsonify(
            {
                "success": cancelled,
                "cancelled": cancelled,
                "message": (
                    "Cancelling preview..." if cancelled else "The preview is no longer active."
                ),
            }
        )
        return _no_store(response), (202 if cancelled else 404)

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
        return safe_error_response(exc)

    @blueprint.errorhandler(ValueError)
    def bad_value(exc: ValueError) -> tuple[Response, int]:
        return safe_error_response(exc)

    @blueprint.errorhandler(SlimReportError)
    def slim_report_error(exc: SlimReportError) -> tuple[Response, int]:
        return safe_error_response(exc)

    @blueprint.errorhandler(TemplateStorageError)
    def template_storage_error(exc: TemplateStorageError) -> tuple[Response, int]:
        return safe_error_response(exc)

    @blueprint.errorhandler(AssetError)
    def asset_error(exc: AssetError) -> tuple[Response, int]:
        return asset_error_response(exc)

    return blueprint


def _status_for_core_error(exc: SlimReportError) -> int:
    if isinstance(
        exc,
        (
            DataSourceNotFoundError,
            DatasetNotFoundError,
            RuntimeParameterDatasetError,
            ViewNotFoundError,
        ),
    ):
        return 404
    if isinstance(exc, MetadataAccessDeniedError):
        return 403
    if isinstance(exc, (DataSourceInUseError, DatasetInUseError)):
        return 409
    if isinstance(exc, (ConnectionTimeoutError, QueryExecutionTimeoutError)):
        return 504
    if isinstance(exc, (CredentialUnavailableError, DatabaseUnavailableError)):
        return 503
    if isinstance(exc, MissingDriverError):
        return 503
    if isinstance(exc, ExporterError):
        return 500
    return 400


def _json_object_request() -> dict[str, Any]:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ValueError("Request payload must be a JSON object.")
    return payload


def _data_source_request(
    designer: SlimReportDesigner,
) -> tuple[dict[str, Any], str, Report]:
    payload = _json_object_request()
    template = payload.get("template")
    template_id = str(payload.get("template_id") or "")
    if isinstance(template, dict):
        template_id = request_template_id(payload, template)
        report = load_report_from_payload(normalize_template_payload(template))
        _inject_runtime_credentials(designer, payload, report)
        return payload, template_id, report
    if template_id:
        report = designer.get_report(template_id)
        _inject_runtime_credentials(designer, payload, report)
        return payload, template_id, report
    raise ValueError("A report template is required for data-source management.")


def _new_report_configuration(value: Any) -> NewReportConfiguration:
    if not isinstance(value, dict):
        raise ValueError("New report configuration must be a JSON object.")
    report_values = value.get("report") if isinstance(value.get("report"), dict) else {}
    page_values = value.get("page") if isinstance(value.get("page"), dict) else {}
    layout_values = value.get("layout") if isinstance(value.get("layout"), dict) else {}
    source_values = value.get("dataSource")
    dataset_values = value.get("dataset")
    data = None
    if source_values is not None or dataset_values is not None:
        if not isinstance(source_values, dict) or not isinstance(dataset_values, dict):
            raise ValueError("New MySQL reports require a data source and dataset.")
        data = NewReportDataConfiguration(
            data_source=ReportDataSource.from_dict(source_values),
            dataset=ReportDataset.from_dict(dataset_values),
        )
    selected_values = layout_values.get("selectedFields", [])
    if not isinstance(selected_values, list):
        raise ValueError("Selected report fields must be a list.")
    return NewReportConfiguration(
        report_name=str(report_values.get("name") or ""),
        description=_optional_text(report_values.get("description")),
        page=NewReportPageConfiguration(
            size=str(page_values.get("size") or "A4"),
            orientation=str(page_values.get("orientation") or "portrait"),
            margin_top=float(page_values.get("marginTop", 24)),
            margin_right=float(page_values.get("marginRight", 24)),
            margin_bottom=float(page_values.get("marginBottom", 24)),
            margin_left=float(page_values.get("marginLeft", 24)),
            width=_optional_float(page_values.get("width")),
            height=_optional_float(page_values.get("height")),
            unit="px",
        ),
        data=data,
        layout=NewReportLayoutConfiguration(
            layout_type=str(layout_values.get("type") or "blank"),
            selected_fields=tuple(
                SelectedReportField(
                    field_name=str(item.get("field") or ""),
                    label=str(item.get("label") or ""),
                    order=int(item.get("order", index)),
                )
                for index, item in enumerate(selected_values)
                if isinstance(item, dict)
            ),
            include_title=bool(layout_values.get("includeTitle", True)),
            include_column_headers=bool(layout_values.get("includeColumnHeaders", True)),
            allow_narrow_columns=bool(layout_values.get("allowNarrowColumns", False)),
        ),
    )


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _create_mysql_command(payload: dict[str, Any]) -> CreateMySQLDataSourceCommand:
    credential_mode = str(payload.get("credentialMode") or "none")
    password: str | None = None
    password_ref: str | None = None
    if credential_mode == "runtimePassword":
        password = _optional_text(payload.get("password"))
    elif credential_mode == "passwordRef":
        password_ref = _optional_text(payload.get("passwordRef"))
    elif credential_mode != "none":
        raise ValueError("Unsupported credential mode.")
    return CreateMySQLDataSourceCommand(
        name=str(payload.get("name") or ""),
        host=str(payload.get("host") or ""),
        port=_integer_value(payload.get("port", 3306), "port"),
        database=str(payload.get("database") or ""),
        username=str(payload.get("username") or ""),
        password=password,
        password_ref=password_ref,
        charset=str(payload.get("charset") or "utf8mb4"),
        connect_timeout=_integer_value(payload.get("connectTimeout", 10), "connectTimeout"),
        query_timeout=_integer_value(payload.get("queryTimeout", 30), "queryTimeout"),
        data_source_id=_optional_text(payload.get("dataSourceId")),
    )


def _update_mysql_command(
    data_source_id: str,
    payload: dict[str, Any],
) -> UpdateMySQLDataSourceCommand:
    credential_mode = payload.get("credentialMode")
    runtime_password: str | None = None
    password_ref: str | None = None
    clear_runtime_password = payload.get("clearRuntimePassword") is True
    clear_password_ref = payload.get("clearPasswordRef") is True
    if credential_mode == "runtimePassword":
        runtime_password = _optional_text(payload.get("password"))
        clear_password_ref = True
    elif credential_mode == "passwordRef":
        password_ref = _optional_text(payload.get("passwordRef"))
        clear_runtime_password = True
    elif credential_mode == "none":
        clear_runtime_password = True
        clear_password_ref = True
    elif credential_mode is not None:
        raise ValueError("Unsupported credential mode.")
    return UpdateMySQLDataSourceCommand(
        data_source_id=data_source_id,
        name=_optional_payload_text(payload, "name"),
        host=_optional_payload_text(payload, "host"),
        port=_optional_payload_integer(payload, "port"),
        database=_optional_payload_text(payload, "database"),
        username=_optional_payload_text(payload, "username"),
        runtime_password=runtime_password,
        password_ref=password_ref,
        clear_runtime_password=clear_runtime_password,
        clear_password_ref=clear_password_ref,
        charset=_optional_payload_text(payload, "charset"),
        connect_timeout=_optional_payload_integer(payload, "connectTimeout"),
        query_timeout=_optional_payload_integer(payload, "queryTimeout"),
    )


def _optional_payload_text(payload: dict[str, Any], key: str) -> str | None:
    if key not in payload:
        return None
    return str(payload[key] or "")


def _optional_payload_integer(payload: dict[str, Any], key: str) -> int | None:
    if key not in payload:
        return None
    return _integer_value(payload[key], key)


def _integer_value(value: object, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer.")
    if isinstance(value, float) and not value.is_integer():
        raise ValueError(f"{field_name} must be an integer.")
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer.") from exc


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _data_source_list_payload(
    designer: SlimReportDesigner,
    report: Report,
) -> dict[str, Any]:
    summaries = designer.data_source_management_service.list_data_sources(report)
    payloads = []
    for summary in summaries:
        if summary.type != "mysql":
            continue
        payload = _data_source_summary_payload(summary)
        source = report.get_data_source(summary.id)
        if source is not None:
            status = credential_resolution_status(source, designer.credential_resolver)
            payload["credentialStatus"] = {
                "configured": status.configured,
                "resolved": status.resolved,
                "source": status.source,
                "message": status.message,
            }
        payloads.append(payload)
    return {
        "ok": True,
        "dataSources": payloads,
    }


def _runtime_report_key(payload: dict[str, Any]) -> str:
    key = _optional_runtime_report_key(payload)
    if key is None:
        raise ValueError("A report session key is required for runtime credentials.")
    return key


def _optional_runtime_report_key(payload: dict[str, Any]) -> str | None:
    key = payload.get("reportSessionKey", payload.get("report_session_key"))
    if key is None or key == "":
        return None
    if not isinstance(key, str) or not key.strip() or "\x00" in key:
        raise ValueError("The report session key is invalid.")
    return key.strip()


def _inject_runtime_credentials(
    designer: SlimReportDesigner,
    payload: dict[str, Any],
    report: Report,
) -> None:
    key = payload.get("reportSessionKey", payload.get("report_session_key"))
    if not isinstance(key, str) or not key.strip():
        return
    for source in report.data_sources:
        password = designer.runtime_credential_store.get_password(key.strip(), source.id)
        if password is not None:
            source.connection.password = password


def _store_source_runtime_password(
    designer: SlimReportDesigner,
    payload: dict[str, Any],
    source: ReportDataSource,
) -> None:
    password = source.connection.password
    if password is None:
        return
    report_key = _optional_runtime_report_key(payload)
    if report_key is None:
        return
    designer.runtime_credential_store.set_password(report_key, source.id, password)


def _clear_source_runtime_password(
    designer: SlimReportDesigner,
    payload: dict[str, Any],
    data_source_id: str,
) -> None:
    key = payload.get("reportSessionKey", payload.get("report_session_key"))
    if isinstance(key, str) and key.strip():
        designer.runtime_credential_store.clear_password(key.strip(), data_source_id)


def _data_source_mutation_payload(
    designer: SlimReportDesigner,
    report: Report,
    source_id: str | None,
    message: str,
) -> dict[str, Any]:
    result = _data_source_list_payload(designer, report)
    sources = result["dataSources"]
    result.update(
        {
            "template": designer.serializer.dump_mapping(report),
            "source": next(
                (source for source in sources if source["id"] == source_id),
                None,
            ),
            "message": message,
        }
    )
    return result


def _data_source_summary_payload(summary: DataSourceSummary) -> dict[str, Any]:
    return {
        "id": summary.id,
        "name": summary.name,
        "type": summary.type,
        "host": summary.host,
        "port": summary.port,
        "database": summary.database,
        "username": summary.username,
        "charset": summary.charset,
        "connectTimeout": summary.connect_timeout,
        "queryTimeout": summary.query_timeout,
        "passwordConfigured": summary.password_configured,
        "passwordRefConfigured": summary.password_ref_configured,
    }


def _query_parameters(payload: dict[str, Any]) -> tuple[QueryParameter, ...]:
    values = payload.get("parameters", [])
    if not isinstance(values, list):
        raise ValueError("parameters must be an array.")
    parameters: list[QueryParameter] = []
    for value in values:
        if not isinstance(value, dict):
            raise ValueError("Every query parameter must be an object.")
        parameters.append(QueryParameter.from_dict(value))
    return tuple(parameters)


def _parameter_values(payload: dict[str, Any]) -> dict[str, object]:
    values = payload.get("parameterValues", {})
    if not isinstance(values, dict):
        raise ValueError("parameterValues must be an object.")
    return {str(key): value for key, value in values.items()}


def _dataset_list_payload(
    designer: SlimReportDesigner,
    report: Report,
) -> dict[str, Any]:
    source_names = {item.id: item.name for item in report.data_sources}
    return {
        "ok": True,
        "datasets": [
            _dataset_summary_payload(item, source_names.get(item.data_source_id, ""))
            for item in designer.data_source_management_service.list_datasets(report)
        ],
    }


def _dataset_summary_payload(summary: DatasetSummary, source_name: str) -> dict[str, Any]:
    return {
        "id": summary.id,
        "name": summary.name,
        "dataSourceId": summary.data_source_id,
        "dataSourceName": source_name,
        "sourceType": summary.source_type,
        "sourceLabel": summary.source_label,
        "fieldCount": summary.field_count,
        "parameterCount": summary.parameter_count,
    }


def _dataset_mutation_payload(
    designer: SlimReportDesigner,
    report: Report,
    configuration: DatasetConfigurationResult,
    message: str,
) -> dict[str, Any]:
    result = _dataset_list_payload(designer, report)
    result.update(
        {
            "template": designer.serializer.dump_mapping(report),
            "dataset": configuration.dataset.to_dict(),
            "warnings": list(configuration.warnings),
            "changes": _field_change_payload(configuration),
            "message": message,
        }
    )
    return result


def _field_change_payload(configuration: DatasetConfigurationResult) -> dict[str, list[str]] | None:
    changes = configuration.changes
    if changes is None:
        return None
    return {
        "added": list(changes.added),
        "removed": list(changes.removed),
        "changed": list(changes.changed),
    }


def _view_schema_payload(schema: DatabaseViewSchema) -> dict[str, Any]:
    return {
        "ok": True,
        "view": {
            "schemaName": schema.view.schema_name,
            "viewName": schema.view.view_name,
            "displayName": schema.view.display_name or schema.view.view_name,
        },
        "fields": [
            {
                "name": column.name,
                "ordinalPosition": column.ordinal_position,
                "databaseType": column.database_type,
                "dataType": column.normalized_type,
                "nullable": column.nullable,
                "length": column.character_maximum_length,
                "precision": column.numeric_precision,
                "scale": column.numeric_scale,
                "comment": column.column_comment,
                "sourceName": column.source_name,
                "warning": (
                    f"Unknown MySQL type {column.database_type!r}."
                    if column.normalized_type == "unknown"
                    else None
                ),
            }
            for column in schema.columns
        ],
    }


def _discovery_payload(result: QueryFieldDiscoveryResult) -> dict[str, Any]:
    return {
        "ok": True,
        "datasetId": result.dataset_id,
        "provider": result.provider,
        "dialect": result.dialect,
        "fields": [
            {
                **field.to_dict(),
                **(
                    {
                        "databaseType": result.columns[index].database_type,
                        "nullable": result.columns[index].nullable,
                        "precision": result.columns[index].precision,
                        "scale": result.columns[index].scale,
                        "length": result.columns[index].length,
                        "sourceName": result.columns[index].source_name,
                        "warning": (
                            f"Unknown MySQL type {result.columns[index].database_type!r}."
                            if result.columns[index].normalized_type == "unknown"
                            else None
                        ),
                    }
                    if index < len(result.columns)
                    else {}
                ),
            }
            for index, field in enumerate(result.fields)
        ],
        "parameters": list(result.parameters),
        "sampleRowCount": result.sample_row_count,
        "elapsedMs": result.elapsed_ms,
        "warnings": list(result.warnings),
    }


def _connection_test_payload(result: ConnectionTestResult) -> dict[str, Any]:
    return {
        "ok": True,
        "success": result.success,
        "provider": result.provider,
        "message": result.message,
        "database": result.database,
        "serverVersion": result.server_version,
        "elapsedMs": result.elapsed_ms,
        "readOnlyVerified": result.read_only_verified,
        "warnings": list(result.warnings),
    }


def render_report_html(report: Report, data: dict[str, Any], designer: SlimReportDesigner) -> str:
    if designer.asset_provider is None:
        return report.render_html(data)
    return report.render_html(data, asset_provider=designer.asset_provider)


def render_report_pdf(report: Report, data: dict[str, Any], designer: SlimReportDesigner) -> bytes:
    if designer.asset_provider is None:
        return report.render_pdf(data)
    return report.render_pdf(data, asset_provider=designer.asset_provider)


def live_preview_failure_response(exc: Exception) -> tuple[Response, int]:
    """Map runtime preview failures without logging request values or raw exceptions."""
    mapped = map_safe_error(exc)
    current_app.logger.warning("Live report preview failed: code=%s.", mapped.code)
    response = jsonify(
        {
            "success": False,
            "error": mapped.to_dict(),
            "error_detail": mapped.to_dict(),
        }
    )
    return _no_store(response), mapped.status


def _live_preview_error(exc: Exception) -> tuple[str, str, int]:
    mapped = map_safe_error(exc)
    return mapped.code, mapped.message, mapped.status


def _runtime_preview_summary_payload(summary: object) -> dict[str, Any]:
    return {
        "datasetId": summary.dataset_id,
        "datasetName": summary.dataset_name,
        "rowCount": summary.row_count,
        "pageCount": summary.page_count,
        "renderedObjectCount": summary.rendered_object_count,
        "truncated": summary.truncated,
        "cancelled": summary.cancelled,
        "elapsedMs": summary.elapsed_ms,
        "warnings": [
            {"code": warning.code, "message": warning.message} for warning in summary.warnings
        ],
    }


def _authoritative_live_preview_report(
    designer: SlimReportDesigner,
    posted_report: Report,
    *,
    template_id: str,
    dataset_id: str | None,
) -> Report:
    """Overlay stored execution metadata while preserving the posted unsaved layout."""
    if not template_id:
        return posted_report
    try:
        stored_report = designer.get_report(template_id)
    except (FileNotFoundError, TemplateNotFoundError):
        return posted_report
    selected_id = dataset_id
    if selected_id is None:
        detail_ids = {
            band.dataset_id
            for band in posted_report.bands
            if band.dataset_id
            and (band.id.casefold() == "detail" or band.type.casefold() == "detail")
        }
        if len(detail_ids) == 1:
            selected_id = next(iter(detail_ids))
    if selected_id is None:
        return posted_report
    stored_dataset = stored_report.get_dataset(selected_id)
    posted_dataset = posted_report.get_dataset(selected_id)
    if stored_dataset is None or posted_dataset is None:
        return posted_report
    dataset_index = next(
        index for index, item in enumerate(posted_report.datasets) if item.id == selected_id
    )
    posted_report.datasets[dataset_index] = copy.deepcopy(stored_dataset)
    stored_source = stored_report.get_data_source(stored_dataset.data_source_id)
    posted_source = posted_report.get_data_source(stored_dataset.data_source_id)
    if stored_source is not None and posted_source is not None:
        source_index = next(
            index
            for index, item in enumerate(posted_report.data_sources)
            if item.id == stored_source.id
        )
        posted_report.data_sources[source_index] = copy.deepcopy(stored_source)
    return posted_report


def _preview_user_key() -> str:
    return str(request.remote_addr or "local")


def _optional_request_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _no_store(response: Response) -> Response:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return response


def render_failure_response(exc: Exception) -> tuple[Response, int]:
    """Return a safe JSON preview/export error without logging request values."""
    mapped = map_safe_error(exc)
    current_app.logger.warning("Slim report preview/export failed: code=%s.", mapped.code)
    return safe_error_response(exc)


def render_route_failure_response(exc: Exception) -> tuple[Response, int] | Response:
    """Return JSON or readable browser errors for GET preview/export routes."""
    mapped = map_safe_error(exc)
    current_app.logger.warning("Slim report route render/export failed: code=%s.", mapped.code)
    if wants_json_response():
        return safe_error_response(exc)
    html = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        "<title>Report Error</title>"
        "<style>body{font-family:Arial,sans-serif;margin:32px;color:#111827;}"
        "code{background:#f1f5f9;padding:2px 4px;border-radius:3px;}</style>"
        "</head><body>"
        f"<h1>Report export failed</h1><p>{escape(mapped.message)}</p>"
        f"<p><code>{escape(mapped.code)}</code></p>"
        "</body></html>"
    )
    return Response(html, status=mapped.status, mimetype="text/html")


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
    del exc_type
    return jsonify(payload), status


def safe_error_response(exc: BaseException) -> tuple[Response, int]:
    mapped = map_safe_error(exc)
    payload = {
        "ok": False,
        "error": mapped.message,
        "error_detail": mapped.to_dict(),
    }
    return jsonify(payload), mapped.status


def _error_code_for_exception(exc: Exception) -> str:
    return map_safe_error(exc).code


def _status_for_exception(exc: Exception) -> int:
    return map_safe_error(exc).status


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
    mapped = map_safe_error(exc)
    return jsonify({"ok": False, "error": mapped.to_dict()}), mapped.status


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
        '<style id="slim-report-print-route-css">'
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
        script = "<script>window.addEventListener('load',function(){window.print();});</script>"
        html = (
            html.replace("</body>", f"{script}</body>", 1) if "</body>" in html else html + script
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
