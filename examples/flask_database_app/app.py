"""SQLite-backed Flask example for Slim Report Designer templates."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from flask import Flask, redirect

REPO_ROOT = Path(__file__).resolve().parents[2]
for package_src in (
    REPO_ROOT / "packages" / "slim_report_core" / "src",
    REPO_ROOT / "packages" / "slim_report_designer_ui",
    REPO_ROOT / "packages" / "slim_report_flask" / "src",
):
    if str(package_src) not in sys.path:
        sys.path.insert(0, str(package_src))

try:
    from sqlalchemy import Boolean, Column, DateTime, Integer, JSON, String, Text, create_engine
    from sqlalchemy.orm import declarative_base, sessionmaker
except ImportError as exc:  # pragma: no cover - exercised manually
    raise RuntimeError(
        "The database example requires SQLAlchemy. Install it with: "
        'python -m pip install -e "packages/slim_report_core[sqlalchemy]"'
    ) from exc

from slim_report_core.storage import FileSystemTemplateProvider, SQLAlchemyTemplateProvider  # noqa: E402
from slim_report_flask import SlimReportDesigner  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent
SAMPLE_TEMPLATE_DIR = REPO_ROOT / "examples" / "flask_app" / "sample_templates"
DATABASE_PATH = BASE_DIR / "report_templates.db"
Base = declarative_base()


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


def create_app() -> Flask:
    """Create the database-backed demo app."""
    app = Flask(__name__)
    session = create_session()
    provider = SQLAlchemyTemplateProvider(
        session,
        ReportTemplate,
        allow_save=True,
        allow_delete=False,
    )
    seed_templates(provider)
    designer = SlimReportDesigner(
        template_provider=provider,
        data_provider=demo_data_provider(provider),
    )
    designer.init_app(app)

    @app.get("/")
    def index():
        return redirect(
            "/report-designer/designer"
            "?template=complete_sprint5_lab_report&order_id=ORD-2026-0001"
        )

    return app


def create_session():
    engine = create_engine(f"sqlite:///{DATABASE_PATH}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def seed_templates(provider: SQLAlchemyTemplateProvider) -> None:
    """Seed selected sample templates into SQLite if they do not exist."""
    source = FileSystemTemplateProvider(SAMPLE_TEMPLATE_DIR)
    for template_id in [
        "complete_sprint5_lab_report",
        "conditional_lab_result",
        "aggregate_grouped_lab_result",
    ]:
        if not provider.exists(template_id):
            provider.save_template(template_id, source.get_template(template_id))


def demo_data_provider(provider: SQLAlchemyTemplateProvider):
    """Return a data provider that customizes order id while leaving LIS logic to the app."""

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


app = create_app()


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
