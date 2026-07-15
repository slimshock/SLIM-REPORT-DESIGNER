from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any

from flask import Flask

from slim_report_core import (
    ConnectionTestResult,
    DataSourceManagementService,
    DataSourceProviderRegistry,
    DiscoveredColumn,
    MySQLDialect,
    ProviderFieldDiscoveryResult,
    QueryExecutionTimeoutError,
    QueryFieldDiscoveryService,
    Report,
    SQLValidator,
)
from slim_report_core.serialization import JSONSerializer
from slim_report_flask import FileSystemTemplateProvider, SlimReportDesigner


class FakeCursor:
    def __init__(self) -> None:
        self.sql = ""

    def execute(self, sql: str, parameters: tuple[object, ...]) -> None:
        del parameters
        self.sql = sql

    def fetchall(self) -> list[dict[str, object]]:
        if "information_schema.VIEWS" in self.sql:
            return [
                {
                    "TABLE_SCHEMA": "lis",
                    "TABLE_NAME": "report_patient_results",
                    "IS_UPDATABLE": "NO",
                    "DEFINER": "report@%",
                    "SECURITY_TYPE": "DEFINER",
                }
            ]
        return [
            {
                "TABLE_SCHEMA": "lis",
                "TABLE_NAME": "report_patient_results",
                "COLUMN_NAME": "patient_id",
                "ORDINAL_POSITION": 1,
                "COLUMN_DEFAULT": None,
                "IS_NULLABLE": "NO",
                "DATA_TYPE": "int",
                "COLUMN_TYPE": "int(11)",
                "CHARACTER_MAXIMUM_LENGTH": None,
                "NUMERIC_PRECISION": 10,
                "NUMERIC_SCALE": 0,
                "DATETIME_PRECISION": None,
                "COLUMN_COMMENT": "Stable patient identifier",
            }
        ]

    def close(self) -> None:
        return None


class FakeConnection:
    def cursor(self) -> FakeCursor:
        return FakeCursor()


class FakeDatasetProvider:
    provider_type = "mysql"
    dialect_name = "mysql"

    def __init__(self) -> None:
        self.bound_parameters: list[dict[str, object]] = []
        self.connection_count = 0

    @contextmanager
    def connection(self, data_source: object) -> Any:
        del data_source
        self.connection_count += 1
        yield FakeConnection()

    def test_connection(self, data_source: object) -> ConnectionTestResult:
        del data_source
        return ConnectionTestResult(
            success=True,
            provider="mysql",
            message="Connection successful.",
            read_only_verified=True,
        )

    def discover_query_fields(
        self,
        *,
        data_source: object,
        sql: str,
        parameters: dict[str, object],
        policy: object,
    ) -> ProviderFieldDiscoveryResult:
        del data_source, policy
        self.bound_parameters.append(parameters)
        if "timeout_query" in sql:
            raise QueryExecutionTimeoutError("The query timed out while discovering fields.")
        columns = (
            DiscoveredColumn(
                name="order_id",
                ordinal_position=1,
                database_type="LONG",
                normalized_type="integer",
                nullable=False,
                source_name="order_id",
            ),
        )
        if "duplicate_alias" in sql:
            columns = (*columns, columns[0])
        return ProviderFieldDiscoveryResult(
            columns=columns,
            sample_row_count=1,
            elapsed_ms=4.2,
        )


def test_dataset_routes_list_views_inspect_and_create_view(tmp_path: Path) -> None:
    app, designer, _provider = create_dataset_app(tmp_path)
    client = app.test_client()
    template = create_source(client, designer)

    empty = post(client, "/datasets/list", template)
    views = post(client, "/data-sources/main_mysql/views/list", template)
    inspected = post(
        client,
        "/data-sources/main_mysql/views/inspect",
        template,
        viewName="report_patient_results",
    )
    created = post(
        client,
        "/datasets/view",
        template,
        name="Patient Results",
        dataSourceId="main_mysql",
        viewName="report_patient_results",
    )

    assert empty.get_json()["datasets"] == []
    assert [item["viewName"] for item in views.get_json()["views"]] == ["report_patient_results"]
    assert "patients" not in views.get_data(as_text=True)
    assert inspected.get_json()["fields"][0] == {
        "comment": "Stable patient identifier",
        "dataType": "integer",
        "databaseType": "int(11)",
        "length": None,
        "name": "patient_id",
        "nullable": False,
        "ordinalPosition": 1,
        "precision": 10,
        "scale": 0,
        "sourceName": "patient_id",
        "warning": None,
    }
    assert created.status_code == 201
    payload = created.get_json()
    assert payload["dataset"]["fields"][0]["name"] == "patient_id"
    assert payload["datasets"][0]["dataSourceName"] == "Main MySQL"
    assert "password" not in created.get_data(as_text=True).lower()


def test_query_validation_detects_parameters_and_rejects_unsafe_sql(tmp_path: Path) -> None:
    app, designer, _provider = create_dataset_app(tmp_path)
    client = app.test_client()
    template = create_source(client, designer)
    query = "SELECT order_id FROM report_orders WHERE day >= :date_from AND id = :client_id"

    valid = post(client, "/query/validate", template, query=query, parameters=[])
    variable = post(client, "/query/validate", template, query="SELECT @@version")
    assignment = post(client, "/query/validate", template, query="SELECT @x := 1")
    multiple = post(client, "/query/validate", template, query="SELECT 1; SELECT 2")

    assert valid.status_code == 200
    assert valid.get_json()["parameters"] == ["date_from", "client_id"]
    assert valid.get_json()["statement"] == "SELECT"
    assert variable.status_code == assignment.status_code == multiple.status_code == 400
    assert variable.get_json()["error_detail"]["code"] == "sql_unsafe"
    assert assignment.get_json()["error_detail"]["code"] == "sql_unsafe"
    assert multiple.get_json()["error_detail"]["code"] == "sql_multiple_statements"
    assert JSONSerializer().load_mapping(template).datasets == []


def test_view_rename_preserves_fields_without_reconnecting(tmp_path: Path) -> None:
    app, designer, provider = create_dataset_app(tmp_path)
    client = app.test_client()
    template = create_source(client, designer)
    created = post(
        client,
        "/datasets/view",
        template,
        name="Patient Results",
        dataSourceId="main_mysql",
        viewName="report_patient_results",
    ).get_json()
    provider.connection_count = 0

    renamed = put(
        client,
        f"/datasets/{created['dataset']['id']}/view",
        created["template"],
        name="Renamed Results",
    )

    assert renamed.status_code == 200
    assert renamed.get_json()["dataset"]["name"] == "Renamed Results"
    assert renamed.get_json()["dataset"]["fields"] == created["dataset"]["fields"]
    assert provider.connection_count == 0


def test_query_discovery_binds_values_but_returns_no_values_or_rows(tmp_path: Path) -> None:
    app, designer, provider = create_dataset_app(tmp_path)
    client = app.test_client()
    template = create_source(client, designer)
    secret_value = "2026-01-01-private"
    response = post(
        client,
        "/query/discover",
        template,
        dataSourceId="main_mysql",
        query="SELECT order_id FROM report_orders WHERE created_at >= :date_from",
        parameters=[date_parameter()],
        parameterValues={"date_from": secret_value},
    )

    assert response.status_code == 400
    assert secret_value not in response.get_data(as_text=True)

    response = post(
        client,
        "/query/discover",
        template,
        dataSourceId="main_mysql",
        query="SELECT order_id FROM report_orders WHERE created_at >= :date_from",
        parameters=[{**date_parameter(), "dataType": "string"}],
        parameterValues={"date_from": secret_value},
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["fields"][0]["name"] == "order_id"
    assert payload["fields"][0]["databaseType"] == "LONG"
    assert payload["fields"][0]["nullable"] is False
    assert "rows" not in payload
    assert secret_value not in response.get_data(as_text=True)
    assert provider.bound_parameters[-1] == {"date_from": secret_value}


def test_query_dataset_create_update_and_delete_preserve_parent_source(tmp_path: Path) -> None:
    app, designer, _provider = create_dataset_app(tmp_path)
    client = app.test_client()
    template = create_source(client, designer)
    created = post(
        client,
        "/datasets/query",
        template,
        name="Daily Orders",
        dataSourceId="main_mysql",
        query="SELECT order_id FROM report_orders WHERE created_at >= :date_from",
        parameters=[date_parameter()],
        parameterValues={"date_from": "2026-01-01"},
    )
    payload = created.get_json()
    dataset_id = payload["dataset"]["id"]
    updated = put(
        client,
        f"/datasets/{dataset_id}/query",
        payload["template"],
        name="Orders by Day",
    )
    deleted = delete(client, f"/datasets/{dataset_id}", updated.get_json()["template"])

    assert created.status_code == 201
    assert payload["dataset"]["fields"][0]["name"] == "order_id"
    assert "parameterValues" not in created.get_data(as_text=True)
    assert updated.get_json()["dataset"]["name"] == "Orders by Day"
    final_template = deleted.get_json()["template"]
    assert final_template.get("datasets", []) == []
    assert [item["id"] for item in final_template["dataSources"]] == ["main_mysql"]


def test_discovery_duplicate_columns_and_timeout_are_safe(tmp_path: Path) -> None:
    app, designer, _provider = create_dataset_app(tmp_path)
    client = app.test_client()
    template = create_source(client, designer)

    duplicate = post(
        client,
        "/query/discover",
        template,
        dataSourceId="main_mysql",
        query="SELECT duplicate_alias FROM report_orders",
        parameters=[],
    )
    timeout = post(
        client,
        "/query/discover",
        template,
        dataSourceId="main_mysql",
        query="SELECT timeout_query FROM report_orders",
        parameters=[],
    )

    assert duplicate.status_code == 400
    assert duplicate.get_json()["error_detail"]["code"] == "dataset_discovery_failed"
    assert timeout.status_code == 504
    assert timeout.get_json()["error_detail"]["code"] == "dataset_timeout"
    assert "traceback" not in timeout.get_data(as_text=True).lower()


def create_dataset_app(
    tmp_path: Path,
) -> tuple[Flask, SlimReportDesigner, FakeDatasetProvider]:
    provider = FakeDatasetProvider()
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
    report.template.metadata.custom["id"] = "dataset-template"
    designer.create_template(JSONSerializer().dump_mapping(report))
    return app, designer, provider


def test_new_report_build_endpoint_revalidates_and_returns_bound_template(
    tmp_path: Path,
) -> None:
    app, designer, provider = create_dataset_app(tmp_path)
    client = app.test_client()
    source_template = create_source(client, designer)
    source = source_template["dataSources"][0]
    response = client.post(
        "/report-designer/api/designer/new-report/build",
        json={
            "template_id": "dataset-template",
            "configuration": {
                "report": {"name": "Orders"},
                "page": {
                    "size": "A4",
                    "orientation": "landscape",
                    "marginTop": 24,
                    "marginRight": 24,
                    "marginBottom": 24,
                    "marginLeft": 24,
                },
                "dataSource": source,
                "dataset": {
                    "id": "orders",
                    "name": "Orders",
                    "dataSourceId": source["id"],
                    "sourceType": "query",
                    "query": "SELECT orderid FROM report_orders WHERE orderdate >= :date_from",
                    "parameters": [date_parameter()],
                    "fields": [{"name": "orderid", "dataType": "integer"}],
                },
                "layout": {
                    "type": "tabular",
                    "selectedFields": [
                        {"field": "orderid", "label": "Order ID", "order": 1}
                    ],
                },
            },
        },
    )

    assert response.status_code == 200
    template = response.get_json()["template"]
    assert template["metadata"]["title"] == "Orders"
    assert template["bands"][1]["dataBinding"] == {"datasetId": "orders"}
    assert template["objects"][-1]["dataBinding"]["field"] == "orderid"
    assert provider.connection_count == 0


def test_runtime_parameter_routes_are_safe_and_do_not_open_database(tmp_path: Path) -> None:
    app, designer, provider = create_dataset_app(tmp_path)
    client = app.test_client()
    template = create_source(client, designer)
    created = post(
        client,
        "/datasets/query",
        template,
        name="Daily Orders",
        dataSourceId="main_mysql",
        query=(
            "SELECT order_id FROM report_orders "
            "WHERE created_at >= :date_from AND client_id = :client_id"
        ),
        parameters=[
            date_parameter(),
            {
                "name": "client_id",
                "dataType": "integer",
                "required": False,
                "default": 12,
                "label": "Client ID",
            },
        ],
        parameterValues={"date_from": "2026-01-01"},
    ).get_json()
    dataset_id = created["dataset"]["id"]
    provider.connection_count = 0

    schema = post(
        client,
        f"/datasets/{dataset_id}/runtime-parameters",
        created["template"],
    )
    valid = post(
        client,
        f"/datasets/{dataset_id}/runtime-parameters/validate",
        created["template"],
        values={"date_from": "2026-07-15"},
    )
    private_value = "private-invalid-client-value"
    invalid = post(
        client,
        f"/datasets/{dataset_id}/runtime-parameters/validate",
        created["template"],
        values={"date_from": "2026-07-15", "client_id": private_value},
    )
    unknown = post(
        client,
        f"/datasets/{dataset_id}/runtime-parameters/validate",
        created["template"],
        values={"date_from": "2026-07-15", "extra": "private-extra-value"},
    )

    assert schema.status_code == 200
    assert [item["name"] for item in schema.get_json()["parameters"]] == [
        "date_from",
        "client_id",
    ]
    assert schema.get_json()["parameters"][1]["default"] == 12
    assert valid.get_json() == {
        "valid": True,
        "datasetId": dataset_id,
        "parameterCount": 2,
        "usedDefaults": ["client_id"],
    }
    assert invalid.status_code == 400
    assert invalid.get_json()["errors"][0]["code"] == "invalid_integer"
    assert private_value not in invalid.get_data(as_text=True)
    assert unknown.status_code == 400
    assert unknown.get_json()["errors"][0]["code"] == "unknown_parameter"
    assert "private-extra-value" not in unknown.get_data(as_text=True)
    assert provider.connection_count == 0
    assert "values" not in valid.get_data(as_text=True).lower()


def test_runtime_parameter_schema_handles_views_and_missing_datasets(tmp_path: Path) -> None:
    app, designer, provider = create_dataset_app(tmp_path)
    client = app.test_client()
    template = create_source(client, designer)
    created = post(
        client,
        "/datasets/view",
        template,
        name="Patient Results",
        dataSourceId="main_mysql",
        viewName="report_patient_results",
    ).get_json()
    dataset_id = created["dataset"]["id"]
    provider.connection_count = 0

    schema = post(
        client,
        f"/datasets/{dataset_id}/runtime-parameters",
        created["template"],
    )
    missing = post(
        client,
        "/datasets/missing/runtime-parameters",
        created["template"],
    )

    assert schema.status_code == 200
    assert schema.get_json()["parameters"] == []
    assert missing.status_code == 404
    assert "values" not in missing.get_data(as_text=True).lower()
    assert provider.connection_count == 0


def create_source(client: Any, designer: SlimReportDesigner) -> dict[str, Any]:
    response = client.post(
        "/report-designer/api/designer/data-sources/mysql",
        json={
            "template_id": "dataset-template",
            "template": designer.get_template("dataset-template"),
            "dataSourceId": "main_mysql",
            "name": "Main MySQL",
            "host": "localhost",
            "port": 3306,
            "database": "lis",
            "username": "reader",
            "credentialMode": "none",
        },
    )
    assert response.status_code == 201
    return response.get_json()["template"]


def post(client: Any, path: str, template: dict[str, Any], **values: object) -> Any:
    return client.post(
        f"/report-designer/api/designer{path}",
        json={"template_id": "dataset-template", "template": template, **values},
    )


def put(client: Any, path: str, template: dict[str, Any], **values: object) -> Any:
    return client.put(
        f"/report-designer/api/designer{path}",
        json={"template_id": "dataset-template", "template": template, **values},
    )


def delete(client: Any, path: str, template: dict[str, Any]) -> Any:
    return client.delete(
        f"/report-designer/api/designer{path}",
        json={"template_id": "dataset-template", "template": template},
    )


def date_parameter() -> dict[str, object]:
    return {
        "name": "date_from",
        "dataType": "date",
        "required": True,
        "label": "Date From",
    }
