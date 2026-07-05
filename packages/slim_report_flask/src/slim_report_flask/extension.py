"""Flask extension for Slim Report Designer."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from flask import Flask

from slim_report_core import (
    DataProviderRegistry,
    Report,
    create_default_template,
    render_html,
    render_pdf,
)
from slim_report_core.serialization import JSONSerializer

from .blueprint import create_blueprint
from .config import DEFAULT_CONFIG
from .storage import TemplateRecord, TemplateStore


class SlimReportDesigner:
    """Flask extension that exposes report template and rendering routes."""

    def __init__(self, app: Flask | None = None) -> None:
        self.app: Flask | None = None
        self.providers = DataProviderRegistry()
        self.template_store: TemplateStore | None = None
        self.serializer = JSONSerializer()

        if app is not None:
            self.init_app(app)

    def init_app(self, app: Flask) -> None:
        """Initialize the extension for a Flask app."""
        for key, value in DEFAULT_CONFIG.items():
            app.config.setdefault(key, value)

        template_dir = app.config["SLIM_REPORT_TEMPLATE_DIR"]
        if template_dir is None:
            template_dir = Path(app.instance_path) / "slim_report_templates"
            app.config["SLIM_REPORT_TEMPLATE_DIR"] = str(template_dir)

        self.app = app
        self.template_store = TemplateStore(Path(template_dir))
        self.template_store.ensure()
        app.extensions["slim_report_designer"] = self

        blueprint = create_blueprint(self)
        app.register_blueprint(
            blueprint,
            url_prefix=app.config["SLIM_REPORT_DESIGNER_URL_PREFIX"],
        )

    def provider(self, name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register a named data provider with decorator syntax."""

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self.providers.register(name, func)
            return func

        return decorator

    def register_provider(self, name: str, func: Callable[..., Any]) -> Callable[..., Any]:
        """Register a named data provider directly."""
        return self.providers.register(name, func)

    def list_templates(self) -> list[TemplateRecord]:
        """Return saved report templates."""
        return self._store().list()

    def create_template(self, payload: dict[str, Any] | None = None) -> TemplateRecord:
        """Create and save a new report template."""
        template_id = _template_id(payload)
        report = (
            self.serializer.load_mapping(payload)
            if payload is not None
            else Report(create_default_template())
        )
        self._store().save(template_id, report)
        return self._store().get(template_id)

    def save_template(self, template_id: str, payload: dict[str, Any]) -> TemplateRecord:
        """Validate and save an existing report template."""
        report = self.serializer.load_mapping(payload)
        self._store().save(template_id, report)
        return self._store().get(template_id)

    def get_report(self, template_id: str) -> Report:
        """Load a saved report template by id."""
        return self._store().load_report(template_id)

    def resolve_data(self, template_id: str, record_id: str) -> Any:
        """Resolve render data using the configured provider for a template."""
        report = self.get_report(template_id)
        provider_name = self._provider_name(template_id, report)
        if provider_name is None:
            return {}
        return self.providers.resolve(provider_name, record_id)

    def render_preview(self, template_id: str, record_id: str) -> str:
        """Render a report preview as HTML."""
        report = self.get_report(template_id)
        data = self.resolve_data(template_id, record_id)
        return render_html(report, data)

    def export_pdf(self, template_id: str, record_id: str) -> bytes:
        """Render a report as PDF bytes."""
        report = self.get_report(template_id)
        data = self.resolve_data(template_id, record_id)
        return render_pdf(report, data)

    def _provider_name(self, template_id: str, report: Report) -> str | None:
        configured = self.app.config if self.app is not None else {}
        template_providers = configured.get("SLIM_REPORT_TEMPLATE_PROVIDERS", {})
        if template_id in template_providers:
            return str(template_providers[template_id])

        metadata_provider = report.metadata.custom.get("provider")
        if metadata_provider:
            return str(metadata_provider)

        default_provider = configured.get("SLIM_REPORT_DEFAULT_PROVIDER")
        if default_provider:
            return str(default_provider)

        provider_names = self.providers.list()
        if len(provider_names) == 1:
            return provider_names[0]

        return None

    def _store(self) -> TemplateStore:
        if self.template_store is None:
            raise RuntimeError("SlimReportDesigner has not been initialized with a Flask app.")
        return self.template_store


def _template_id(payload: dict[str, Any] | None) -> str:
    if payload is not None:
        metadata = payload.get("metadata")
        if isinstance(metadata, dict):
            custom = metadata.get("custom")
            if isinstance(custom, dict) and custom.get("id"):
                return str(custom["id"])

    return uuid.uuid4().hex
