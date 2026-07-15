from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import Flask

from slim_report_core import (
    Band,
    DatasetExecutionCancellationToken,
    DatasetField,
    DatasetFieldBinding,
    MySQLConnectionConfig,
    Report,
    ReportDataset,
    ReportDataSource,
    RuntimePreviewResult,
    RuntimePreviewSummary,
    RuntimePreviewWarning,
    TextObject,
)
from slim_report_core.serialization import JSONSerializer
from slim_report_flask import (
    FileSystemTemplateProvider,
    PreviewCancellationRegistry,
    SlimReportDesigner,
)


class FakeRuntimeRenderService:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def render_html(self, report: Report, **kwargs: Any) -> RuntimePreviewResult:
        self.calls.append({"report": report, **kwargs})
        if self.error is not None:
            raise self.error
        return RuntimePreviewResult(
            html="<!doctype html><p>Alice &lt;script&gt;</p>",
            summary=RuntimePreviewSummary(
                dataset_id="patients",
                dataset_name="Patients",
                row_count=1,
                page_count=1,
                rendered_object_count=3,
                truncated=True,
                cancelled=False,
                elapsed_ms=4.5,
                warnings=(
                    RuntimePreviewWarning(
                        "preview_truncated", "Preview is limited to 500 rows."
                    ),
                ),
            ),
        )


def report_payload() -> dict[str, Any]:
    report = Report(
        bands=[Band("detail", "detail", y=0, height=30, dataset_id="patients")],
        data_sources=[
            ReportDataSource(
                id="mysql",
                name="MySQL",
                type="mysql",
                connection=MySQLConnectionConfig(
                    database="lis", username="reader", password_ref="MYSQL_PASSWORD"
                ),
            )
        ],
        datasets=[
            ReportDataset(
                id="patients",
                name="Patients",
                data_source_id="mysql",
                source_type="query",
                query="SELECT name FROM report_patients WHERE day = :day",
                fields=[DatasetField(name="name", data_type="string", nullable=True)],
            )
        ],
    )
    item = TextObject("{{patients.name}}", id="name", height=20, band_id="detail")
    item.dataset_binding = DatasetFieldBinding("patients", "name")
    report.add_object(item)
    return JSONSerializer().dump_mapping(report)


def create_app(
    tmp_path: Path,
    service: FakeRuntimeRenderService,
    *,
    auth_required: Any = None,
) -> tuple[Flask, SlimReportDesigner]:
    app = Flask(__name__)
    app.config["TESTING"] = True
    designer = SlimReportDesigner(
        template_provider=FileSystemTemplateProvider(tmp_path / "templates", allow_save=True),
        runtime_report_render_service=service,  # type: ignore[arg-type]
        auth_required=auth_required,
    )
    designer.init_app(app)
    return app, designer


def test_live_preview_adapter_returns_no_store_safe_summary_and_cleans_registry(
    tmp_path: Path,
) -> None:
    service = FakeRuntimeRenderService()
    authorized: list[bool] = []
    app, designer = create_app(
        tmp_path,
        service,
        auth_required=lambda: authorized.append(True) is None or True,
    )
    request_id = "5db2c690-c5f9-4c6d-a267-c1b005294980"
    response = app.test_client().post(
        "/report-designer/api/designer/preview/live",
        json={
            "requestId": request_id,
            "datasetId": "patients",
            "parameterValues": {"day": "2026-07-15"},
            "options": {"maxRows": 50},
            "template": report_payload(),
        },
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Pragma"] == "no-cache"
    assert payload["success"] is True
    assert payload["summary"]["rowCount"] == 1
    assert payload["summary"]["truncated"] is True
    assert payload["html"].endswith("&lt;script&gt;</p>")
    assert "2026-07-15" not in response.get_data(as_text=True)
    assert "SELECT name" not in response.get_data(as_text=True)
    assert authorized
    assert service.calls[0]["options"].max_rows == 50
    assert service.calls[0]["parameter_values"] == {"day": "2026-07-15"}
    assert not designer.preview_cancellation_registry.cancel(
        request_id, user_key="127.0.0.1"
    )


def test_live_preview_adapter_conceals_unexpected_errors_and_values(tmp_path: Path) -> None:
    service = FakeRuntimeRenderService(RuntimeError("driver failed around secret-value"))
    app, _designer = create_app(tmp_path, service)
    response = app.test_client().post(
        "/report-designer/api/designer/preview/live",
        json={
            "requestId": "5db2c690-c5f9-4c6d-a267-c1b005294981",
            "datasetId": "patients",
            "parameterValues": {"day": "secret-value"},
            "template": report_payload(),
        },
    )

    assert response.status_code == 500
    assert response.headers["Cache-Control"] == "no-store"
    assert response.get_json()["error"] == {
        "code": "server_error",
        "message": "The operation could not be completed.",
        "details": [],
    }
    assert "secret-value" not in response.get_data(as_text=True)
    assert "driver failed" not in response.get_data(as_text=True)


def test_saved_dataset_execution_metadata_overrides_posted_sql(tmp_path: Path) -> None:
    service = FakeRuntimeRenderService()
    app, designer = create_app(tmp_path, service)
    stored = report_payload()
    stored["datasets"][0]["query"] = "SELECT name FROM approved_report_patients"
    designer.save_template_mapping("saved-report", stored)
    posted = report_payload()
    posted["datasets"][0]["query"] = "SELECT secret FROM unrestricted_table"

    response = app.test_client().post(
        "/report-designer/api/designer/preview/live",
        json={
            "requestId": "5db2c690-c5f9-4c6d-a267-c1b005294989",
            "template_id": "saved-report",
            "datasetId": "patients",
            "parameterValues": {"day": "2026-07-15"},
            "template": posted,
        },
    )

    assert response.status_code == 200
    rendered_report = service.calls[0]["report"]
    assert rendered_report.datasets[0].query == "SELECT name FROM approved_report_patients"
    assert "unrestricted_table" not in response.get_data(as_text=True)


def test_cancellation_endpoint_signals_only_owned_token(tmp_path: Path) -> None:
    app, designer = create_app(tmp_path, FakeRuntimeRenderService())
    token = DatasetExecutionCancellationToken()
    request_id = designer.preview_cancellation_registry.register(
        user_key="127.0.0.1",
        report_key="report",
        token=token,
        request_id="5db2c690-c5f9-4c6d-a267-c1b005294982",
    )
    response = app.test_client().post(
        f"/report-designer/api/designer/preview/{request_id}/cancel"
    )

    assert response.status_code == 202
    assert response.get_json()["cancelled"] is True
    assert token.is_cancelled
    designer.preview_cancellation_registry.remove(request_id)


def test_preview_cancellation_registry_validates_ownership_and_removal() -> None:
    registry = PreviewCancellationRegistry(expiry_seconds=30)
    token = DatasetExecutionCancellationToken()
    request_id = registry.register(
        user_key="alice",
        report_key="report",
        token=token,
        request_id="5db2c690-c5f9-4c6d-a267-c1b005294983",
    )
    assert not registry.cancel(request_id, user_key="bob")
    assert not token.is_cancelled
    assert registry.cancel(request_id, user_key="alice")
    registry.remove(request_id)
    registry.remove(request_id)
    assert not registry.cancel(request_id, user_key="alice")
