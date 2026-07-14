"""Flask example for database template storage and MySQL metadata discovery."""

# Direct execution must bootstrap this checkout before importing possibly stale installed packages.
# ruff: noqa: E402

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
for package_source in (
    REPO_ROOT / "packages" / "slim_report_core" / "src",
    REPO_ROOT / "packages" / "slim_report_designer_ui",
    REPO_ROOT / "packages" / "slim_report_flask" / "src",
):
    source_path = str(package_source)
    if source_path not in sys.path:
        sys.path.insert(0, source_path)

from dotenv import load_dotenv
from flask import Flask, render_template
from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from slim_report_core import (
    DataSourceConnectionError,
    DataSourceMetadataError,
    DataSourceValidationError,
    InvalidViewIdentifierError,
    MetadataAccessDeniedError,
    MetadataAccessPolicy,
    MissingDriverError,
    MySQLConnectionConfig,
    MySQLDataSourceProvider,
    MySQLMetadataService,
    ReportDataSource,
    ViewNotFoundError,
)
from slim_report_core.storage import FileSystemTemplateProvider, SQLAlchemyTemplateProvider
from slim_report_flask import SlimReportDesigner

BASE_DIR = Path(__file__).resolve().parent
SAMPLE_TEMPLATE_DIR = REPO_ROOT / "examples" / "flask_app" / "sample_templates"
LIS_TEMPLATE_DIR = REPO_ROOT / "examples" / "lis_templates"
DATABASE_PATH = BASE_DIR / "report_templates.db"
Base = declarative_base()


class ExampleConfigurationError(Exception):
    """Raised when local example environment variables are incomplete or invalid."""


@dataclass(frozen=True)
class ExampleServices:
    """Reusable service objects; none of these retain a live MySQL connection."""

    data_source: ReportDataSource | None
    provider: MySQLDataSourceProvider | None
    metadata_service: MySQLMetadataService | None
    policy: MetadataAccessPolicy | None
    setup_error: str | None = None


class ReportTemplate(Base):  # type: ignore[valid-type,misc]
    """Example SQLAlchemy model. Apps may use their own model shape."""

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


def create_app(
    *,
    data_source: ReportDataSource | None = None,
    provider: MySQLDataSourceProvider | None = None,
    metadata_service: MySQLMetadataService | None = None,
    policy: MetadataAccessPolicy | None = None,
    enable_designer: bool = True,
) -> Flask:
    """Create the database-backed designer and metadata demonstration app."""
    app = Flask(__name__)
    try:
        app.config["DEBUG"] = parse_boolean_environment("SLIM_REPORT_EXAMPLE_DEBUG", default=False)
        services = build_example_services(
            data_source=data_source,
            provider=provider,
            metadata_service=metadata_service,
            policy=policy,
        )
    except ExampleConfigurationError as exc:
        app.config["DEBUG"] = False
        services = ExampleServices(
            data_source=None,
            provider=None,
            metadata_service=None,
            policy=None,
            setup_error=str(exc),
        )
    app.extensions["slim_report_database_example"] = services

    if enable_designer:
        configure_designer(app)

    @app.context_processor
    def example_context() -> dict[str, bool]:
        return {"designer_enabled": enable_designer}

    @app.get("/")
    def index():
        return render_template(
            "index.html",
            services=services,
            connection=services.data_source.connection if services.data_source else None,
        )

    @app.post("/connection/test")
    def test_connection():
        ready = require_services(services)
        result = ready.provider.test_connection(ready.data_source)
        status = 200 if result.success else 503
        return render_template("connection_test.html", result=result), status

    @app.get("/views")
    def list_views():
        ready = require_services(services)
        views = ready.metadata_service.list_views(ready.data_source)
        return render_template("views.html", views=views)

    @app.get("/views/<view_name>")
    def inspect_view(view_name: str):
        ready = require_services(services)
        schema = ready.metadata_service.inspect_view(ready.data_source, view_name)
        return render_template("view_schema.html", schema=schema)

    register_error_handlers(app)
    return app


def build_example_services(
    *,
    data_source: ReportDataSource | None = None,
    provider: MySQLDataSourceProvider | None = None,
    metadata_service: MySQLMetadataService | None = None,
    policy: MetadataAccessPolicy | None = None,
) -> ExampleServices:
    """Build reusable provider services without opening a connection."""
    try:
        configured_source = data_source or build_data_source()
        configured_policy = policy or build_metadata_policy()
        configured_provider = provider or MySQLDataSourceProvider()
        configured_metadata = metadata_service or MySQLMetadataService(
            provider=configured_provider,
            policy=configured_policy,
        )
        return ExampleServices(
            data_source=configured_source,
            provider=configured_provider,
            metadata_service=configured_metadata,
            policy=configured_policy,
        )
    except (ExampleConfigurationError, DataSourceValidationError, ValueError) as exc:
        return ExampleServices(
            data_source=None,
            provider=None,
            metadata_service=None,
            policy=None,
            setup_error=str(exc),
        )


def build_data_source() -> ReportDataSource:
    """Build MySQL metadata configuration using environment variables only."""
    database = required_environment("SLIM_REPORT_MYSQL_DATABASE")
    username = required_environment("SLIM_REPORT_MYSQL_USERNAME")
    required_environment("SLIM_REPORT_MYSQL_PASSWORD", secret=True)
    port_text = os.getenv("SLIM_REPORT_MYSQL_PORT", "3306").strip()
    try:
        port = int(port_text)
    except ValueError as exc:
        raise ExampleConfigurationError(
            "SLIM_REPORT_MYSQL_PORT must be an integer between 1 and 65535."
        ) from exc

    connection = MySQLConnectionConfig(
        host=os.getenv("SLIM_REPORT_MYSQL_HOST", "localhost").strip() or "localhost",
        port=port,
        database=database,
        username=username,
        password_ref="SLIM_REPORT_MYSQL_PASSWORD",
    )
    return ReportDataSource(
        id="example_mysql",
        name="Example MySQL",
        type="mysql",
        connection=connection,
    )


def build_metadata_policy() -> MetadataAccessPolicy:
    """Build a views-only, system-schema-safe metadata policy from the environment."""
    return MetadataAccessPolicy(
        views_only=True,
        allow_cross_schema=parse_boolean_environment(
            "SLIM_REPORT_ALLOW_CROSS_SCHEMA",
            default=False,
        ),
        allowed_schemas=parse_csv_environment("SLIM_REPORT_ALLOWED_SCHEMAS"),
        allowed_view_prefixes=parse_csv_environment(
            "SLIM_REPORT_ALLOWED_VIEW_PREFIXES",
            default=("report_", "vw_report_"),
        ),
        allowed_view_names=parse_csv_environment("SLIM_REPORT_ALLOWED_VIEW_NAMES"),
        include_system_schemas=False,
    )


def required_environment(name: str, *, secret: bool = False) -> str:
    """Read a required variable without including secret values in errors."""
    value = os.getenv(name)
    if value is None or not value.strip():
        label = "required secret variable" if secret else "required environment variable"
        raise ExampleConfigurationError(f"The {label} {name} is not configured.")
    return value.strip()


def parse_csv_environment(name: str, *, default: tuple[str, ...] = ()) -> tuple[str, ...]:
    """Parse a comma-separated allowlist while ignoring empty items."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return tuple(item.strip() for item in raw.split(",") if item.strip())


def parse_boolean_environment(name: str, *, default: bool) -> bool:
    """Parse deterministic true and false environment spellings."""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    normalized = raw.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ExampleConfigurationError(f"{name} must be one of: true, false, 1, 0, yes, no, on, off.")


def load_example_environment(path: Path | None = None) -> bool:
    """Load local example values without overriding variables already exported by the shell."""
    environment_path = path or BASE_DIR / ".env"
    return load_dotenv(dotenv_path=environment_path, override=False)


def require_services(services: ExampleServices) -> ExampleServices:
    """Fail safely when local environment setup was incomplete."""
    if services.setup_error is not None:
        raise ExampleConfigurationError(services.setup_error)
    if (
        services.data_source is None
        or services.provider is None
        or services.metadata_service is None
    ):
        raise ExampleConfigurationError("The MySQL example services are not configured.")
    return services


def register_error_handlers(app: Flask) -> None:
    """Render concise project errors without raw driver or credential details."""

    def error_page(error: Exception, title: str, status: int):
        app.logger.warning("%s (%s).", title, type(error).__name__)
        return render_template("error.html", title=title, message=str(error), status=status), status

    @app.errorhandler(InvalidViewIdentifierError)
    def invalid_identifier(error: InvalidViewIdentifierError):
        return error_page(error, "Invalid view identifier", 400)

    @app.errorhandler(ViewNotFoundError)
    def missing_view(error: ViewNotFoundError):
        return error_page(error, "Reporting view not found", 404)

    @app.errorhandler(MetadataAccessDeniedError)
    def metadata_denied(error: MetadataAccessDeniedError):
        return error_page(error, "Metadata access denied", 403)

    @app.errorhandler(MissingDriverError)
    def missing_driver(error: MissingDriverError):
        return error_page(error, "MySQL driver unavailable", 500)

    @app.errorhandler(DataSourceMetadataError)
    def metadata_error(error: DataSourceMetadataError):
        return error_page(error, "Metadata operation failed", 502)

    @app.errorhandler(DataSourceConnectionError)
    def connection_error(error: DataSourceConnectionError):
        return error_page(error, "MySQL connection unavailable", 503)

    @app.errorhandler(DataSourceValidationError)
    def data_source_error(error: DataSourceValidationError):
        return error_page(error, "Invalid data-source configuration", 500)

    @app.errorhandler(ExampleConfigurationError)
    def configuration_error(error: ExampleConfigurationError):
        return error_page(error, "Example setup required", 500)


def configure_designer(app: Flask) -> None:
    """Preserve the existing SQLite template-storage designer integration."""
    session = create_session()
    template_provider = SQLAlchemyTemplateProvider(
        session,
        ReportTemplate,
        allow_save=True,
        allow_delete=False,
    )
    seed_templates(template_provider)
    designer = SlimReportDesigner(
        template_provider=template_provider,
        data_provider=demo_data_provider(template_provider),
    )
    designer.init_app(app)


def create_session():
    engine = create_engine(f"sqlite:///{DATABASE_PATH}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def seed_templates(provider: SQLAlchemyTemplateProvider) -> None:
    """Seed selected sample templates into SQLite if they do not exist."""
    source = FileSystemTemplateProvider(SAMPLE_TEMPLATE_DIR)
    for template_id in (
        "complete_sprint5_lab_report",
        "conditional_lab_result",
        "aggregate_grouped_lab_result",
    ):
        if not provider.exists(template_id):
            provider.save_template(template_id, source.get_template(template_id))
    lis_source = FileSystemTemplateProvider(LIS_TEMPLATE_DIR)
    for template_id in ("lab_result_hematology_two_column",):
        if not provider.exists(template_id):
            provider.save_template(template_id, lis_source.get_template(template_id))


def demo_data_provider(provider: SQLAlchemyTemplateProvider):
    """Customize order id while leaving LIS business logic to the application."""

    def data_provider(template_id: str, request_args: Any, request_json: Any) -> dict[str, Any]:
        order_id = _request_value("order_id", request_args, request_json) or "ORD-2026-0001"
        data = provider.get_sample_data(template_id)
        order = dict(data.get("order", {}))
        order["id"] = str(order_id)
        data["order"] = order
        data["barcode_value"] = str(order_id)
        data["qr_value"] = f"https://example.local/verify/{order_id}"
        return data

    return data_provider


def _request_value(name: str, request_args: Any, request_json: Any) -> Any:
    if hasattr(request_args, "get") and request_args.get(name):
        return request_args.get(name)
    if isinstance(request_json, dict):
        if request_json.get(name):
            return request_json[name]
        request_arg_payload = request_json.get("request_args")
        if isinstance(request_arg_payload, dict) and request_arg_payload.get(name):
            return request_arg_payload[name]
    return None


load_example_environment()
app = create_app()


if __name__ == "__main__":
    app.run(debug=app.debug, use_reloader=False)
