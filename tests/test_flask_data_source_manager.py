from __future__ import annotations

from pathlib import Path

from flask import Flask

from slim_report_core import (
    ConnectionTestResult,
    DatasetSourceType,
    DataSourceManagementService,
    DataSourceProviderRegistry,
    MissingDriverError,
    MySQLDialect,
    QueryFieldDiscoveryService,
    Report,
    ReportDataset,
    SQLValidator,
)
from slim_report_core.serialization import JSONSerializer
from slim_report_flask import FileSystemTemplateProvider, SlimReportDesigner


class FakeMySQLProvider:
    provider_type = "mysql"
    dialect_name = "mysql"

    def __init__(self, *, missing_driver: bool = False) -> None:
        self.missing_driver = missing_driver
        self.tested_hosts: list[str] = []

    def test_connection(self, data_source: object) -> ConnectionTestResult:
        if self.missing_driver:
            raise MissingDriverError("The MySQL driver is not installed.")
        connection = data_source.connection  # type: ignore[attr-defined]
        self.tested_hosts.append(connection.host)
        success = connection.host != "unreachable"
        return ConnectionTestResult(
            success=success,
            provider="mysql",
            message=(
                "Connection successful." if success else "The MySQL server could not be reached."
            ),
            server_version="8.0.36" if success else None,
            database=connection.database if success else None,
            elapsed_ms=12.5,
            read_only_verified=success,
        )


def test_data_source_api_lists_creates_and_serializes_without_password(tmp_path: Path) -> None:
    app, designer, _provider = create_data_source_app(tmp_path)
    client = app.test_client()
    template = designer.get_template("data-template")

    empty = client.post(
        "/report-designer/api/designer/data-sources/list",
        json={"template_id": "data-template", "template": template},
    )
    created = client.post(
        "/report-designer/api/designer/data-sources/mysql",
        json={
            "template_id": "data-template",
            "template": template,
            **mysql_payload(password="top-secret", credentialMode="runtimePassword"),
        },
    )

    assert empty.status_code == 200
    assert empty.get_json()["dataSources"] == []
    assert created.status_code == 201
    payload = created.get_json()
    assert payload["source"]["name"] == "Main MySQL"
    assert payload["source"]["passwordConfigured"] is True
    assert payload["source"]["charset"] == "utf8mb4"
    assert "top-secret" not in created.get_data(as_text=True)
    connection = payload["template"]["dataSources"][0]["connection"]
    assert "password" not in connection
    assert designer.get_report("data-template").data_sources == []


def test_runtime_password_store_is_report_session_scoped_and_clearable(tmp_path: Path) -> None:
    app, designer, _provider = create_data_source_app(tmp_path)
    client = app.test_client()
    template = designer.get_template("data-template")
    session_key = "6cf2b4a4-48da-476c-aeb8-2f4ea20d417c"
    created_response = client.post(
        "/report-designer/api/designer/data-sources/mysql",
        json={
            "template_id": "data-template",
            "template": template,
            "reportSessionKey": session_key,
            **mysql_payload(password="session-secret", credentialMode="runtimePassword"),
        },
    )
    created = created_response.get_json()
    source_id = created["source"]["id"]

    same_session = client.post(
        "/report-designer/api/designer/data-sources/list",
        json={
            "template_id": "data-template",
            "template": created["template"],
            "reportSessionKey": session_key,
        },
    ).get_json()["dataSources"][0]
    other_session = client.post(
        "/report-designer/api/designer/data-sources/list",
        json={
            "template_id": "data-template",
            "template": created["template"],
            "reportSessionKey": "07ac9b7d-e6c5-48ca-8a65-b08c8e8e564a",
        },
    ).get_json()["dataSources"][0]
    cleared = client.post(
        "/report-designer/api/designer/credentials/clear",
        json={
            "template_id": "data-template",
            "reportSessionKey": session_key,
            "dataSourceId": source_id,
        },
    )

    assert created_response.status_code == 201
    assert "session-secret" not in created_response.get_data(as_text=True)
    assert same_session["credentialStatus"]["source"] == "runtime"
    assert other_session["credentialStatus"]["source"] == "none"
    assert cleared.status_code == 200
    assert designer.runtime_credential_store.get_password(session_key, source_id) is None


def test_reopen_readiness_and_save_validation_are_safe_and_offline(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.delenv("SLIM_REPORT_MYSQL_PASSWORD", raising=False)
    app, designer, provider = create_data_source_app(tmp_path)
    client = app.test_client()
    created = create_source(client, designer, credentialMode="passwordRef")
    request_payload = {
        "template_id": "data-template",
        "template": created["template"],
        "reportSessionKey": "92c8758b-a469-44a5-8461-65734e005db6",
    }

    reopened = client.post("/report-designer/api/designer/reopen/inspect", json=request_payload)
    save_validation = client.post(
        "/report-designer/api/designer/save/validate", json=request_payload
    )

    assert reopened.status_code == 200
    assert reopened.get_json()["canEdit"] is True
    assert reopened.get_json()["canPreview"] is False
    assert save_validation.get_json()["canSave"] is True
    assert save_validation.get_json()["runtimeReady"] is False
    assert provider.tested_hosts == []


def test_data_source_api_updates_atomically_and_explicitly_clears_credentials(
    tmp_path: Path,
) -> None:
    app, designer, _provider = create_data_source_app(tmp_path)
    client = app.test_client()
    created = create_source(client, designer, credentialMode="passwordRef")
    source_id = created["source"]["id"]

    updated = client.put(
        f"/report-designer/api/designer/data-sources/{source_id}",
        json={
            "template_id": "data-template",
            "template": created["template"],
            "name": "Renamed MySQL",
        },
    )
    cleared = client.put(
        f"/report-designer/api/designer/data-sources/{source_id}",
        json={
            "template_id": "data-template",
            "template": updated.get_json()["template"],
            "credentialMode": "none",
        },
    )

    assert updated.status_code == 200
    updated_source = updated.get_json()["source"]
    assert updated_source["name"] == "Renamed MySQL"
    assert updated_source["host"] == "localhost"
    assert updated_source["passwordRefConfigured"] is True
    assert cleared.status_code == 200
    cleared_payload = cleared.get_json()
    assert cleared_payload["source"]["passwordRefConfigured"] is False
    assert "passwordRef" not in cleared_payload["template"]["dataSources"][0]["connection"]


def test_connection_tests_are_safe_and_do_not_mutate_the_report(tmp_path: Path) -> None:
    app, designer, provider = create_data_source_app(tmp_path)
    client = app.test_client()
    original = designer.get_template("data-template")

    unsaved = client.post(
        "/report-designer/api/designer/data-sources/test",
        json={
            "template_id": "data-template",
            **mysql_payload(password="temporary", credentialMode="runtimePassword"),
        },
    )
    created = create_source(client, designer, credentialMode="passwordRef")
    source_id = created["source"]["id"]
    saved = client.post(
        f"/report-designer/api/designer/data-sources/{source_id}/test",
        json={
            "template_id": "data-template",
            "template": created["template"],
        },
    )

    assert unsaved.status_code == 200
    assert unsaved.get_json()["readOnlyVerified"] is True
    assert saved.status_code == 200
    assert saved.get_json()["serverVersion"] == "8.0.36"
    assert provider.tested_hosts == ["localhost", "localhost"]
    assert "temporary" not in unsaved.get_data(as_text=True)
    assert designer.get_template("data-template") == original


def test_invalid_create_and_missing_source_return_safe_errors(tmp_path: Path) -> None:
    app, designer, _provider = create_data_source_app(tmp_path)
    client = app.test_client()
    template = designer.get_template("data-template")

    invalid = client.post(
        "/report-designer/api/designer/data-sources/mysql",
        json={
            "template_id": "data-template",
            "template": template,
            **mysql_payload(port=70000),
        },
    )
    missing = client.post(
        "/report-designer/api/designer/data-sources/missing/test",
        json={"template_id": "data-template", "template": template},
    )

    assert invalid.status_code == 400
    assert invalid.get_json()["error_detail"]["code"] == "data_source_invalid"
    assert missing.status_code == 404
    assert missing.get_json()["ok"] is False
    assert "traceback" not in missing.get_data(as_text=True).lower()
    assert designer.get_report("data-template").data_sources == []


def test_delete_rejects_in_use_source_and_never_cascades(tmp_path: Path) -> None:
    app, designer, _provider = create_data_source_app(tmp_path)
    client = app.test_client()
    created = create_source(client, designer)
    source_id = created["source"]["id"]
    report = JSONSerializer().load_mapping(created["template"])
    report.add_dataset(
        ReportDataset(
            name="Patient Results",
            data_source_id=source_id,
            source_type=DatasetSourceType.VIEW,
            view_name="patient_results",
        )
    )
    in_use_template = JSONSerializer().dump_mapping(report)

    blocked = client.delete(
        f"/report-designer/api/designer/data-sources/{source_id}",
        json={"template_id": "data-template", "template": in_use_template},
    )
    removed = client.delete(
        f"/report-designer/api/designer/data-sources/{source_id}",
        json={"template_id": "data-template", "template": created["template"]},
    )

    assert blocked.status_code == 409
    assert blocked.get_json()["dependents"] == ["Patient Results"]
    assert removed.status_code == 200
    assert removed.get_json()["dataSources"] == []
    assert removed.get_json()["deletedId"] == source_id


def test_missing_mysql_driver_is_mapped_without_internal_details(tmp_path: Path) -> None:
    app, _designer, _provider = create_data_source_app(tmp_path, missing_driver=True)
    response = app.test_client().post(
        "/report-designer/api/designer/data-sources/test",
        json={"template_id": "data-template", **mysql_payload()},
    )

    assert response.status_code == 503
    assert response.get_json()["error"] == "The MySQL driver is not installed."
    assert "traceback" not in response.get_data(as_text=True).lower()


def create_data_source_app(
    tmp_path: Path,
    *,
    missing_driver: bool = False,
) -> tuple[Flask, SlimReportDesigner, FakeMySQLProvider]:
    provider = FakeMySQLProvider(missing_driver=missing_driver)
    registry = DataSourceProviderRegistry()
    registry.register(provider)
    validator = SQLValidator(MySQLDialect())
    service = DataSourceManagementService(
        provider_registry=registry,
        sql_validator=validator,
        query_discovery_service=QueryFieldDiscoveryService(registry, validator),
    )
    app = Flask(__name__)
    app.config["TESTING"] = True
    designer = SlimReportDesigner(
        template_provider=FileSystemTemplateProvider(tmp_path / "templates", allow_save=True),
        data_source_management_service=service,
    )
    designer.init_app(app)
    report = Report()
    report.template.metadata.title = "Data Sources"
    report.template.metadata.custom["id"] = "data-template"
    designer.create_template(JSONSerializer().dump_mapping(report))
    return app, designer, provider


def create_source(
    client: object,
    designer: SlimReportDesigner,
    **overrides: object,
) -> dict[str, object]:
    response = client.post(  # type: ignore[attr-defined]
        "/report-designer/api/designer/data-sources/mysql",
        json={
            "template_id": "data-template",
            "template": designer.get_template("data-template"),
            **mysql_payload(**overrides),
        },
    )
    assert response.status_code == 201
    return response.get_json()


def mysql_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "Main MySQL",
        "host": "localhost",
        "port": 3306,
        "database": "lis",
        "username": "report_user",
        "credentialMode": "passwordRef",
        "password": None,
        "passwordRef": "SLIM_REPORT_MYSQL_PASSWORD",
        "charset": "utf8mb4",
        "connectTimeout": 10,
        "queryTimeout": 30,
    }
    payload.update(overrides)
    return payload
