from __future__ import annotations

from pathlib import Path

import pytest
from examples.flask_database_app import app as example

from slim_report_core import (
    ConnectionTestResult,
    DatabaseColumnInfo,
    DatabaseViewInfo,
    DatabaseViewSchema,
    InvalidViewIdentifierError,
    MetadataAccessDeniedError,
    MetadataAccessPolicy,
    MetadataQueryError,
    MissingDriverError,
    MySQLConnectionConfig,
    ReportDataSource,
    ViewNotFoundError,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


class FakeProvider:
    provider_type = "mysql"

    def __init__(self, result: ConnectionTestResult | None = None) -> None:
        self.result = result or ConnectionTestResult(
            success=True,
            provider="mysql",
            message="MySQL connection succeeded.",
            server_version="8.0.36",
            database="slim_report_test",
            elapsed_ms=3.25,
            read_only_verified=True,
        )
        self.calls = 0
        self.error: Exception | None = None

    def test_connection(self, data_source: ReportDataSource) -> ConnectionTestResult:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.result


class FakeMetadataService:
    def __init__(
        self,
        *,
        views: tuple[DatabaseViewInfo, ...] = (),
        schema: DatabaseViewSchema | None = None,
    ) -> None:
        self.views = views
        self.schema = schema
        self.list_calls = 0
        self.inspect_calls: list[str] = []
        self.list_error: Exception | None = None
        self.inspect_error: Exception | None = None

    def list_views(self, data_source: ReportDataSource) -> tuple[DatabaseViewInfo, ...]:
        self.list_calls += 1
        if self.list_error is not None:
            raise self.list_error
        return self.views

    def inspect_view(self, data_source: ReportDataSource, view_name: str) -> DatabaseViewSchema:
        self.inspect_calls.append(view_name)
        if self.inspect_error is not None:
            raise self.inspect_error
        if any(token in view_name for token in (";", "--", "/*", "`")):
            raise InvalidViewIdentifierError("The view identifier is invalid.")
        if self.schema is None:
            raise ViewNotFoundError(f"The reporting view {view_name!r} was not found.")
        return self.schema


def report_data_source(secret: str = "browser-test-secret") -> ReportDataSource:
    return ReportDataSource(
        id="example_mysql",
        name="Example MySQL",
        type="mysql",
        connection=MySQLConnectionConfig(
            host="localhost",
            port=3306,
            database="slim_report_test",
            username="slim_report_reader",
            password=secret,
        ),
    )


def report_schema() -> DatabaseViewSchema:
    view = DatabaseViewInfo(
        schema_name="slim_report_test",
        view_name="report_patient_results",
    )
    return DatabaseViewSchema(
        view=view,
        columns=(
            DatabaseColumnInfo(
                name="patient_id",
                ordinal_position=1,
                database_type="bigint unsigned",
                normalized_type="integer",
                nullable=False,
                numeric_precision=20,
                numeric_scale=0,
                column_comment="Patient identifier",
            ),
            DatabaseColumnInfo(
                name="active",
                ordinal_position=2,
                database_type="tinyint(1)",
                normalized_type="boolean",
                nullable=False,
            ),
            DatabaseColumnInfo(
                name="payload",
                ordinal_position=3,
                database_type="future_type(7)",
                normalized_type="unknown",
                nullable=True,
                character_maximum_length=255,
            ),
        ),
    )


def create_test_app(
    *,
    provider: FakeProvider | None = None,
    metadata: FakeMetadataService | None = None,
    policy: MetadataAccessPolicy | None = None,
):
    fake_provider = provider or FakeProvider()
    fake_metadata = metadata or FakeMetadataService(
        views=(
            DatabaseViewInfo(
                schema_name="slim_report_test",
                view_name="report_patient_results",
            ),
        ),
        schema=report_schema(),
    )
    app = example.create_app(
        data_source=report_data_source(),
        provider=fake_provider,  # type: ignore[arg-type]
        metadata_service=fake_metadata,  # type: ignore[arg-type]
        policy=policy or MetadataAccessPolicy(allowed_view_prefixes=("report_",)),
        enable_designer=False,
    )
    app.config.update(TESTING=True)
    return app, fake_provider, fake_metadata


def test_home_page_loads_without_exposing_password_or_reference() -> None:
    app, _, _ = create_test_app()

    response = app.test_client().get("/")
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "MySQL read-only metadata explorer" in text
    assert "slim_report_test" in text
    assert "slim_report_reader" in text
    assert "report_" in text
    assert "Cross-schema access" in text
    assert "Disabled" in text
    assert "browser-test-secret" not in text
    assert "SLIM_REPORT_MYSQL_PASSWORD" not in text
    assert "Metadata only" in text


def test_connection_test_success_uses_post_and_displays_safe_result() -> None:
    app, provider, metadata = create_test_app()
    client = app.test_client()

    assert client.get("/connection/test").status_code == 405
    response = client.post("/connection/test")
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Connection succeeded" in text
    assert "8.0.36" in text
    assert "3.250 ms" in text
    assert "Read-only verified" in text
    assert provider.calls == 1
    assert metadata.list_calls == 0
    assert metadata.inspect_calls == []


def test_connection_test_failure_is_safe_and_does_not_query_metadata() -> None:
    result = ConnectionTestResult(
        success=False,
        provider="mysql",
        message="MySQL authentication failed.",
        elapsed_ms=1.5,
    )
    provider = FakeProvider(result)
    metadata = FakeMetadataService()
    app, _, _ = create_test_app(provider=provider, metadata=metadata)

    response = app.test_client().post("/connection/test")
    text = response.get_data(as_text=True)

    assert response.status_code == 503
    assert "Connection failed" in text
    assert "MySQL authentication failed." in text
    assert "browser-test-secret" not in text
    assert metadata.list_calls == 0


def test_missing_driver_uses_safe_error_page() -> None:
    provider = FakeProvider()
    provider.error = MissingDriverError("Install the optional mysql dependency.")
    app, _, _ = create_test_app(provider=provider)

    response = app.test_client().post("/connection/test")

    assert response.status_code == 503
    assert "MySQL driver unavailable" in response.get_data(as_text=True)


def test_view_list_displays_only_core_service_results() -> None:
    metadata = FakeMetadataService(
        views=(
            DatabaseViewInfo("slim_report_test", "report_patient_results"),
            DatabaseViewInfo(
                "slim_report_test",
                "report_daily_sales",
                security_type="INVOKER",
                is_updatable=False,
            ),
        )
    )
    app, _, _ = create_test_app(metadata=metadata)

    response = app.test_client().get("/views")
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "report_patient_results" in text
    assert "report_daily_sales" in text
    assert "INVOKER" in text
    assert "patients</" not in text
    assert metadata.list_calls == 1
    assert metadata.inspect_calls == []


def test_empty_view_list_is_handled_cleanly() -> None:
    app, _, _ = create_test_app(metadata=FakeMetadataService())

    response = app.test_client().get("/views")

    assert response.status_code == 200
    assert "No approved views found" in response.get_data(as_text=True)


def test_view_schema_displays_normalized_types_and_no_rows() -> None:
    metadata = FakeMetadataService(schema=report_schema())
    app, _, _ = create_test_app(metadata=metadata)

    response = app.test_client().get("/views/report_patient_results")
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "3 columns" in text
    assert "bigint unsigned" in text
    assert "integer" in text
    assert "tinyint(1)" in text
    assert "boolean" in text
    assert "future_type(7)" in text
    assert "unknown" in text
    assert "Patient identifier" in text
    assert "reporting view" in text
    assert "itself was not executed" in text
    assert metadata.inspect_calls == ["report_patient_results"]
    assert metadata.list_calls == 0


@pytest.mark.parametrize(
    "path",
    [
        "/views/report_view%3B",
        "/views/report_view%20--%20comment",
        "/views/%60report_view%60",
    ],
)
def test_invalid_identifier_returns_safe_400(path: str) -> None:
    app, _, _ = create_test_app()

    response = app.test_client().get(path)
    text = response.get_data(as_text=True)

    assert response.status_code == 400
    assert "Invalid view identifier" in text
    assert "Traceback" not in text


def test_missing_view_returns_safe_404() -> None:
    metadata = FakeMetadataService()
    app, _, _ = create_test_app(metadata=metadata)

    response = app.test_client().get("/views/report_missing")

    assert response.status_code == 404
    assert "Reporting view not found" in response.get_data(as_text=True)


def test_metadata_access_failure_is_safe_and_raw_cause_is_hidden() -> None:
    secret = "raw-driver-secret"
    raw_error = RuntimeError(secret)
    safe_error = MetadataAccessDeniedError("Metadata access is not allowed.")
    safe_error.__cause__ = raw_error
    metadata = FakeMetadataService()
    metadata.list_error = safe_error
    app, _, _ = create_test_app(metadata=metadata)

    response = app.test_client().get("/views")
    text = response.get_data(as_text=True)

    assert response.status_code == 403
    assert "Metadata access denied" in text
    assert "Metadata access is not allowed." in text
    assert secret not in text
    assert "Traceback" not in text


def test_generic_metadata_failure_does_not_render_raw_details() -> None:
    metadata = FakeMetadataService()
    error = MetadataQueryError("The MySQL metadata query failed.")
    error.__cause__ = RuntimeError("password=raw-secret")
    metadata.inspect_error = error
    app, _, _ = create_test_app(metadata=metadata)

    response = app.test_client().get("/views/report_patient_results")
    text = response.get_data(as_text=True)

    assert response.status_code == 503
    assert "Metadata operation failed" in text
    assert "password=raw-secret" not in text


def test_jinja_autoescaping_protects_displayed_metadata() -> None:
    metadata = FakeMetadataService(
        views=(DatabaseViewInfo("slim_report_test", "<script>alert(1)</script>"),)
    )
    app, _, _ = create_test_app(metadata=metadata)

    text = app.test_client().get("/views").get_data(as_text=True)

    assert "<script>alert(1)</script>" not in text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in text


def test_no_custom_sql_or_report_row_routes_exist() -> None:
    app, provider, metadata = create_test_app()
    client = app.test_client()

    for path in ("/query", "/sql", "/preview", "/rows", "/export"):
        assert client.get(path).status_code == 404
        assert client.post(path).status_code == 404

    assert provider.calls == 0
    assert metadata.list_calls == 0
    assert metadata.inspect_calls == []
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert rules >= {"/", "/connection/test", "/views", "/views/<view_name>"}


def test_diagnostics_are_loopback_only_and_never_expose_runtime_values() -> None:
    app, _, _ = create_test_app()
    local = app.test_client().get("/diagnostics")
    remote = app.test_client().get(
        "/diagnostics", environ_base={"REMOTE_ADDR": "192.0.2.10"}
    )

    assert local.status_code == 200
    payload = local.get_json()
    assert payload["designerAssetsAvailable"] is True
    assert payload["credentialReferenceConfigured"] is False
    assert payload["connectionTest"] is True
    assert payload["readOnlyVerified"] is True
    serialized = local.get_data(as_text=True)
    assert "browser-test-secret" not in serialized
    assert "SELECT" not in serialized
    assert "previewHtml" not in serialized
    assert remote.status_code == 403


def test_missing_environment_renders_useful_setup_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "SLIM_REPORT_MYSQL_DATABASE",
        "SLIM_REPORT_MYSQL_USERNAME",
        "SLIM_REPORT_MYSQL_PASSWORD",
    ):
        monkeypatch.delenv(name, raising=False)
    app = example.create_app(enable_designer=False)
    app.config.update(TESTING=True)

    response = app.test_client().get("/")
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Setup required" in text
    assert "SLIM_REPORT_MYSQL_DATABASE" in text
    assert "browser-test-secret" not in text
    assert app.test_client().get("/views").status_code == 503


def test_environment_builders_use_password_reference_and_safe_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values = {
        "SLIM_REPORT_MYSQL_HOST": "db.internal",
        "SLIM_REPORT_MYSQL_PORT": "3307",
        "SLIM_REPORT_MYSQL_DATABASE": "reporting",
        "SLIM_REPORT_MYSQL_USERNAME": "reader",
        "SLIM_REPORT_MYSQL_PASSWORD": "environment-secret",
        "SLIM_REPORT_ALLOWED_VIEW_PREFIXES": " report_, vw_report_, ",
        "SLIM_REPORT_ALLOWED_VIEW_NAMES": "special_view,",
        "SLIM_REPORT_ALLOW_CROSS_SCHEMA": "yes",
        "SLIM_REPORT_ALLOWED_SCHEMAS": "archive, reporting",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)

    source = example.build_data_source()
    policy = example.build_metadata_policy()

    assert source.connection.host == "db.internal"
    assert source.connection.port == 3307
    assert source.connection.password is None
    assert source.connection.password_ref == "SLIM_REPORT_MYSQL_PASSWORD"
    assert "environment-secret" not in repr(source.connection.to_dict())
    assert policy.views_only
    assert not policy.include_system_schemas
    assert policy.allow_cross_schema
    assert policy.allowed_schemas == ("archive", "reporting")
    assert policy.allowed_view_prefixes == ("report_", "vw_report_")
    assert policy.allowed_view_names == ("special_view",)


def test_local_dotenv_file_is_loaded_without_overriding_exported_values(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    environment_file = tmp_path / ".env"
    environment_file.write_text(
        "\n".join(
            (
                "SLIM_REPORT_MYSQL_DATABASE=dotenv_reporting",
                "SLIM_REPORT_MYSQL_USERNAME=dotenv_reader",
                "SLIM_REPORT_MYSQL_PASSWORD=dotenv-secret",
            )
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("SLIM_REPORT_MYSQL_DATABASE", raising=False)
    monkeypatch.delenv("SLIM_REPORT_MYSQL_PASSWORD", raising=False)
    monkeypatch.setenv("SLIM_REPORT_MYSQL_USERNAME", "exported_reader")

    assert example.load_example_environment(environment_file)
    source = example.build_data_source()

    assert source.connection.database == "dotenv_reporting"
    assert source.connection.username == "exported_reader"
    assert source.connection.password is None
    assert source.connection.password_ref == "SLIM_REPORT_MYSQL_PASSWORD"
    assert "dotenv-secret" not in repr(source.connection.to_dict())


@pytest.mark.parametrize("value", ["maybe", "enabled", "2"])
def test_invalid_boolean_environment_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    monkeypatch.setenv("SLIM_REPORT_ALLOW_CROSS_SCHEMA", value)

    with pytest.raises(example.ExampleConfigurationError, match="must be one of"):
        example.build_metadata_policy()


def test_invalid_debug_environment_renders_setup_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SLIM_REPORT_EXAMPLE_DEBUG", "unsafe")

    app = example.create_app(enable_designer=False)
    app.config.update(TESTING=True)
    response = app.test_client().get("/")

    assert response.status_code == 200
    assert "SLIM_REPORT_EXAMPLE_DEBUG must be one of" in response.get_data(as_text=True)
    assert not app.debug


def test_invalid_port_environment_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLIM_REPORT_MYSQL_DATABASE", "reporting")
    monkeypatch.setenv("SLIM_REPORT_MYSQL_USERNAME", "reader")
    monkeypatch.setenv("SLIM_REPORT_MYSQL_PASSWORD", "secret")
    monkeypatch.setenv("SLIM_REPORT_MYSQL_PORT", "not-a-number")

    with pytest.raises(example.ExampleConfigurationError, match="must be an integer"):
        example.build_data_source()


def test_designer_integration_remains_available() -> None:
    response = example.app.test_client().get("/report-designer/designer")

    assert response.status_code == 200
    assert "SLIM_REPORT_API_BASE" in response.get_data(as_text=True)


def test_demo_uses_normal_installed_package_resolution() -> None:
    source = (REPO_ROOT / "examples/flask_database_app/app.py").read_text(encoding="utf-8")

    assert "sys.path" not in source
    assert "PYTHONPATH" not in source
    assert "packages/slim_report_core" not in source
