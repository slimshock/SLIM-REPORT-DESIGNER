"""Flask extension for Slim Report Designer."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from inspect import signature
from pathlib import Path
from typing import Any

from flask import Flask, request

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
from .storage import FileSystemTemplateProvider, TemplateProvider, TemplateRecord, _record_from_summary

DataProvider = Callable[[str, Any, Any], Any]
AuthHook = Callable[[], bool]
PermissionHook = Callable[[str], bool]
CsrfTokenProvider = Callable[[], str | None]


class SlimReportDesigner:
    """Flask extension that exposes report template and rendering routes."""

    def __init__(
        self,
        app: Flask | None = None,
        *,
        template_provider: TemplateProvider | None = None,
        data_provider: DataProvider | None = None,
        url_prefix: str | None = None,
        auth_required: AuthHook | None = None,
        can_view_template: PermissionHook | None = None,
        can_edit_template: PermissionHook | None = None,
        can_export_template: PermissionHook | None = None,
        csrf_token_provider: CsrfTokenProvider | None = None,
        csrf_header_name: str = "X-CSRFToken",
    ) -> None:
        self.app: Flask | None = None
        self.providers = DataProviderRegistry()
        self.template_provider = template_provider
        self.data_provider = data_provider
        self.url_prefix = url_prefix
        self.auth_required = auth_required
        self.can_view_template = can_view_template
        self.can_edit_template = can_edit_template
        self.can_export_template = can_export_template
        self.csrf_token_provider = csrf_token_provider
        self.csrf_header_name = csrf_header_name
        self.serializer = JSONSerializer()

        if app is not None:
            self.init_app(app)

    def init_app(self, app: Flask) -> None:
        """Initialize the extension for a Flask app."""
        for key, value in DEFAULT_CONFIG.items():
            app.config.setdefault(key, value)

        if self.template_provider is None:
            template_dir = app.config["SLIM_REPORT_TEMPLATE_DIR"]
            if template_dir is None:
                template_dir = Path(app.instance_path) / "slim_report_templates"
                app.config["SLIM_REPORT_TEMPLATE_DIR"] = str(template_dir)
            self.template_provider = FileSystemTemplateProvider(template_dir, allow_save=True)

        self.app = app
        if hasattr(self.template_provider, "ensure"):
            self.template_provider.ensure()
        app.extensions["slim_report_designer"] = self

        blueprint = create_blueprint(self)
        app.register_blueprint(
            blueprint,
            url_prefix=self.route_prefix,
        )

    @property
    def route_prefix(self) -> str:
        configured = self.url_prefix
        if configured is None and self.app is not None:
            configured = self.app.config.get("SLIM_REPORT_DESIGNER_URL_PREFIX")
        return str(configured or DEFAULT_CONFIG["SLIM_REPORT_DESIGNER_URL_PREFIX"]).rstrip("/")

    @property
    def save_enabled(self) -> bool:
        provider = self._provider()
        return bool(getattr(provider, "allow_save", True))

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
        return [_record_from_summary(item) for item in self._provider().list_templates()]

    def list_template_summaries(self) -> list[dict[str, Any]]:
        """Return API-friendly template summaries."""
        return [record.to_api_dict() for record in self.list_templates()]

    def create_template(self, payload: dict[str, Any] | None = None) -> TemplateRecord:
        """Create and save a new report template."""
        template_id = _template_id(payload)
        report = (
            self.serializer.load_mapping(payload)
            if payload is not None
            else Report(create_default_template())
        )
        saved = self._provider().save_template(template_id, self.serializer.dump_mapping(report))
        return _record_from_template(template_id, saved)

    def save_template(self, template_id: str, payload: dict[str, Any]) -> TemplateRecord:
        """Validate and save an existing report template."""
        report = self.serializer.load_mapping(payload)
        saved = self._provider().save_template(template_id, self.serializer.dump_mapping(report))
        return _record_from_template(template_id, saved)

    def save_template_mapping(self, template_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Validate, save, and return a template mapping."""
        report = self.serializer.load_mapping(payload)
        return self._provider().save_template(template_id, self.serializer.dump_mapping(report))

    def get_template(self, template_id: str) -> dict[str, Any]:
        """Load a saved template mapping by id."""
        return self._provider().get_template(template_id)

    def get_report(self, template_id: str) -> Report:
        """Load a saved report template by id."""
        return self.serializer.load_mapping(self.get_template(template_id))

    def resolve_data(
        self,
        template_id: str,
        record_id: str = "sample",
        *,
        explicit_data: Any | None = None,
        request_args: Any | None = None,
        request_json: Any | None = None,
        report: Report | None = None,
    ) -> Any:
        """Resolve render data using the configured provider for a template."""
        if isinstance(explicit_data, dict):
            return explicit_data
        report = report or self.get_report(template_id)
        if self.data_provider is not None:
            data = self._call_data_provider(template_id, request_args, request_json)
            if isinstance(data, dict):
                return data
        provider_name = self._provider_name(template_id, report)
        if provider_name is None:
            sample = getattr(report, "data", {}).get("sample")
            if isinstance(sample, dict):
                return sample
            return {}
        return self.providers.resolve(provider_name, record_id)

    def render_preview(self, template_id: str, record_id: str) -> str:
        """Render a report preview as HTML."""
        report = self.get_report(template_id)
        data = self.resolve_data(template_id, record_id, request_args=request.args, report=report)
        return render_html(report, data)

    def export_pdf(self, template_id: str, record_id: str) -> bytes:
        """Render a report as PDF bytes."""
        report = self.get_report(template_id)
        data = self.resolve_data(template_id, record_id, request_args=request.args, report=report)
        return render_pdf(report, data)

    def is_authenticated(self) -> bool:
        """Return whether the current request is authenticated."""
        if self.auth_required is None:
            return True
        return bool(self.auth_required())

    def can_view(self, template_id: str) -> bool:
        return self._permission(self.can_view_template, template_id)

    def can_edit(self, template_id: str) -> bool:
        return self._permission(self.can_edit_template, template_id)

    def can_export(self, template_id: str) -> bool:
        return self._permission(self.can_export_template, template_id)

    def csrf_config(self) -> dict[str, str]:
        """Return frontend CSRF config."""
        if self.csrf_token_provider is None:
            return {}
        token = self.csrf_token_provider()
        if not token:
            return {}
        return {"csrfHeaderName": self.csrf_header_name, "csrfToken": str(token)}

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

    def _provider(self) -> TemplateProvider:
        if self.template_provider is None:
            raise RuntimeError("SlimReportDesigner has not been initialized with a Flask app.")
        return self.template_provider

    def _call_data_provider(self, template_id: str, request_args: Any, request_json: Any) -> Any:
        provider = self.data_provider
        if provider is None:
            return {}
        try:
            params = signature(provider).parameters
            if len(params) <= 1:
                return provider(template_id)  # type: ignore[misc]
            if len(params) == 2:
                return provider(template_id, request_args)  # type: ignore[misc]
        except (TypeError, ValueError):
            pass
        return provider(template_id, request_args, request_json)

    def _permission(self, hook: PermissionHook | None, template_id: str) -> bool:
        if hook is None:
            return True
        return bool(hook(template_id))


def _template_id(payload: dict[str, Any] | None) -> str:
    if payload is not None:
        metadata = payload.get("metadata")
        if isinstance(metadata, dict):
            custom = metadata.get("custom")
            if isinstance(custom, dict) and custom.get("id"):
                return str(custom["id"])

    return uuid.uuid4().hex


def _record_from_template(template_id: str, template: dict[str, Any]) -> TemplateRecord:
    metadata = template.get("metadata") if isinstance(template.get("metadata"), dict) else {}
    title = str(metadata.get("title") or metadata.get("name") or template_id)
    description = str(metadata.get("description") or "")
    return TemplateRecord(id=template_id, title=title, path=Path(""), description=description)
