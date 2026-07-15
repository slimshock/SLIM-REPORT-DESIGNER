"""Safe report persistence, compatibility, and reopen inspection."""

from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .bindings import ReportBindingService
from .constants import DEFAULT_REPORT_VERSION
from .data_sources import (
    CredentialResolver,
    DatasetField,
    DatasetSourceType,
    EnvironmentCredentialResolver,
    MySQLConnectionConfig,
    ReportDataSource,
)
from .exceptions import ReportSerializationError
from .runtime_parameters import RuntimeParameterError, RuntimeParameterResolver
from .sql import MySQLDialect, SQLValidationError, SQLValidator


@dataclass(frozen=True)
class CredentialPersistencePolicy:
    """Controls which credential metadata can cross persistence boundaries."""

    allow_password_reference: bool = True
    allow_runtime_password_serialization: bool = False
    reject_legacy_plaintext_passwords: bool = True
    redact_credentials_in_errors: bool = True
    redact_credentials_in_logs: bool = True
    clear_runtime_password_on_reload: bool = True

    def __post_init__(self) -> None:
        for name, value in vars(self).items():
            if not isinstance(value, bool):
                raise TypeError(f"{name} must be boolean.")
        if self.allow_runtime_password_serialization:
            raise ValueError("Runtime password serialization is not supported.")


@dataclass(frozen=True)
class CredentialResolutionStatus:
    """Credential-safe runtime resolution status."""

    configured: bool
    resolved: bool
    source: str | None
    message: str


class CompositeCredentialResolver:
    """Resolve from an ordered set of resolvers without retaining secrets."""

    source_label = "host"

    def __init__(self, resolvers: tuple[CredentialResolver, ...]) -> None:
        self.resolvers = tuple(resolvers)

    def resolve(
        self,
        reference: str,
        *,
        data_source: ReportDataSource | None = None,
    ) -> str | None:
        for resolver in self.resolvers:
            value = _call_resolver(resolver, reference, data_source=data_source)
            if value is not None:
                return value
        return None


@dataclass(frozen=True)
class TemplateCompatibilityResult:
    source_version: str
    target_version: str
    migrated: bool
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class TemplateSecurityInspectionResult:
    safe: bool
    issues: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReportReopenIssue:
    code: str
    severity: str
    message: str
    data_source_id: str | None = None
    dataset_id: str | None = None
    object_id: str | None = None

    def to_dict(self) -> dict[str, str]:
        return {
            key: value
            for key, value in {
                "code": self.code,
                "severity": self.severity,
                "message": self.message,
                "dataSourceId": self.data_source_id,
                "datasetId": self.dataset_id,
                "objectId": self.object_id,
            }.items()
            if value is not None
        }


@dataclass(frozen=True)
class ReportReopenInspectionResult:
    valid: bool
    can_edit: bool
    can_preview: bool
    issues: tuple[ReportReopenIssue, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "canEdit": self.can_edit,
            "canPreview": self.can_preview,
            "issues": [issue.to_dict() for issue in self.issues],
        }


@dataclass(frozen=True)
class ReportPreviewReadinessResult:
    ready: bool
    dataset_id: str | None
    issues: tuple[ReportReopenIssue, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "datasetId": self.dataset_id,
            "issues": [issue.to_dict() for issue in self.issues],
        }


@dataclass(frozen=True)
class ReportSaveValidationResult:
    can_save: bool
    structurally_valid: bool
    runtime_ready: bool
    errors: tuple[ReportReopenIssue, ...] = ()
    warnings: tuple[ReportReopenIssue, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "canSave": self.can_save,
            "structurallyValid": self.structurally_valid,
            "runtimeReady": self.runtime_ready,
            "errors": [issue.to_dict() for issue in self.errors],
            "warnings": [issue.to_dict() for issue in self.warnings],
        }


@dataclass(frozen=True)
class DatasetFreshnessResult:
    dataset_id: str
    checked: bool
    fresh: bool
    added_fields: tuple[str, ...] = ()
    removed_fields: tuple[str, ...] = ()
    changed_fields: tuple[str, ...] = ()
    affected_object_ids: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "datasetId": self.dataset_id,
            "checked": self.checked,
            "fresh": self.fresh,
            "addedFields": list(self.added_fields),
            "removedFields": list(self.removed_fields),
            "changedFields": list(self.changed_fields),
            "affectedObjectIds": list(self.affected_object_ids),
            "warnings": list(self.warnings),
        }


class DatasetFreshnessService:
    """Compare stored and explicitly discovered fields without mutation."""

    def __init__(self, binding_service: ReportBindingService | None = None) -> None:
        self.binding_service = binding_service or ReportBindingService()

    def compare(
        self,
        report: Any,
        dataset_id: str,
        discovered_fields: Sequence[DatasetField],
        *,
        warnings: Sequence[str] = (),
    ) -> DatasetFreshnessResult:
        dataset = report.get_dataset(dataset_id)
        if dataset is None:
            return DatasetFreshnessResult(
                dataset_id, False, False, warnings=("The dataset is no longer available.",)
            )
        before = {field.name.casefold(): field for field in dataset.fields}
        after = {field.name.casefold(): field for field in discovered_fields}
        added = tuple(after[key].name for key in after.keys() - before.keys())
        removed = tuple(before[key].name for key in before.keys() - after.keys())
        changed = tuple(
            after[key].name
            for key in after.keys() & before.keys()
            if before[key].data_type != after[key].data_type
            or before[key].nullable != after[key].nullable
        )
        affected = tuple(
            obj.id
            for obj in self.binding_service.dataset_references(report, dataset_id)
            if obj.dataset_binding.field.casefold()
            in {name.casefold() for name in removed + changed}
        )
        return DatasetFreshnessResult(
            dataset_id,
            True,
            not (added or removed or changed),
            added,
            removed,
            changed,
            affected,
            tuple(warnings),
        )


def inspect_template_security(mapping: Mapping[str, Any]) -> TemplateSecurityInspectionResult:
    """Return paths to transient or secret fields without reading their values."""
    forbidden = {
        "password",
        "runtimepassword",
        "resolvedpassword",
        "parametervalues",
        "runtimevalues",
        "previewhtml",
        "connectionobject",
        "cursorobject",
        "connectiontestresult",
        "readonlyverificationresult",
        "latesterror",
        "loadingstate",
        "previewstate",
    }
    issues: list[str] = []

    def visit(value: Any, path: str) -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                key_text = str(key)
                child_path = f"{path}.{key_text}" if path else key_text
                if key_text.replace("_", "").casefold() in forbidden:
                    issues.append(child_path)
                visit(child, child_path)
        elif isinstance(value, (list, tuple)):
            for index, child in enumerate(value):
                visit(child, f"{path}[{index}]")

    visit(mapping, "")
    return TemplateSecurityInspectionResult(not issues, tuple(issues))


def prepare_template_for_load(
    mapping: Mapping[str, Any],
    policy: CredentialPersistencePolicy | None = None,
) -> tuple[dict[str, Any], TemplateCompatibilityResult, tuple[ReportReopenIssue, ...]]:
    """Copy, normalize legacy keys, and strip unsafe credential fields."""
    active_policy = policy or CredentialPersistencePolicy()
    data = copy.deepcopy(dict(mapping))
    source_version = str(data.get("version") or "0.1")
    if _major_version(source_version) > _major_version(DEFAULT_REPORT_VERSION):
        raise ReportSerializationError(
            "This report template was created by a newer version of SLIM REPORT DESIGNER."
        )
    warnings: list[str] = []
    issues: list[ReportReopenIssue] = []
    if "dataSources" not in data and isinstance(data.get("data_sources"), list):
        data["dataSources"] = data.pop("data_sources")
        warnings.append("Legacy data-source keys were normalized.")
    for source in data.get("dataSources", ()):
        if not isinstance(source, dict):
            continue
        connection = source.get("connection")
        locations = [source]
        if isinstance(connection, dict):
            locations.append(connection)
        removed = False
        for location in locations:
            if "password" in location:
                location.pop("password", None)
                removed = True
            if not active_policy.allow_password_reference:
                location.pop("passwordRef", None)
                location.pop("password_ref", None)
        if removed:
            warnings.append("A legacy plaintext password was removed during import.")
            issues.append(
                ReportReopenIssue(
                    "legacy_plaintext_password_removed",
                    "warning",
                    "A legacy plaintext password was removed. Configure a runtime credential.",
                    data_source_id=str(source.get("id") or "") or None,
                )
            )
    compatibility = TemplateCompatibilityResult(
        source_version,
        DEFAULT_REPORT_VERSION,
        source_version != DEFAULT_REPORT_VERSION or bool(warnings),
        tuple(dict.fromkeys(warnings)),
    )
    return data, compatibility, tuple(issues)


def create_persistable_report_snapshot(report: Any) -> Any:
    """Return a detached report copy made through the secret-stripping serializer."""
    from .serialization import JSONSerializer

    serializer = JSONSerializer()
    return serializer.load_mapping(serializer.dump_mapping(report))


class ReportTemplateReopenService:
    """Inspect a loaded report without database or SQL execution."""

    def __init__(
        self,
        *,
        credential_resolver: CredentialResolver | None = None,
        binding_service: ReportBindingService | None = None,
        data_management_service: Any | None = None,
    ) -> None:
        self.credential_resolver = credential_resolver
        self.binding_service = binding_service or ReportBindingService()
        self.data_management_service = data_management_service
        self.sql_validator = SQLValidator(MySQLDialect())
        self.parameter_resolver = RuntimeParameterResolver()

    def inspect(self, report: Any) -> ReportReopenInspectionResult:
        issues = list(getattr(report, "_reopen_migration_issues", ()))
        sources = {source.id: source for source in report.data_sources}
        for source in report.data_sources:
            if source.type != "mysql":
                issues.append(
                    self._issue(
                        "unsupported_provider",
                        "error",
                        "The saved data-source provider is not supported.",
                        source=source.id,
                    )
                )
                continue
            if not isinstance(source.connection, MySQLConnectionConfig):
                issues.append(
                    self._issue(
                        "invalid_data_source",
                        "error",
                        "The saved data-source configuration is invalid.",
                        source=source.id,
                    )
                )
                continue
            status = credential_resolution_status(source, self.credential_resolver)
            if status.configured and not status.resolved:
                issues.append(
                    self._issue(
                        "credential_unresolved",
                        "error",
                        "The MySQL credential could not be resolved.",
                        source=source.id,
                    )
                )

        for dataset in report.datasets:
            if dataset.data_source_id not in sources:
                issues.append(
                    self._issue(
                        "missing_dataset_data_source",
                        "error",
                        "The dataset references a missing data source.",
                        dataset=dataset.id,
                    )
                )
            if not dataset.fields:
                issues.append(
                    self._issue(
                        "dataset_has_no_fields",
                        "error",
                        "The dataset has no discovered fields.",
                        dataset=dataset.id,
                    )
                )
            if dataset.source_type is DatasetSourceType.QUERY:
                try:
                    self.sql_validator.validate_dataset(dataset)
                except SQLValidationError:
                    issues.append(
                        self._issue(
                            "invalid_query",
                            "error",
                            "The dataset contains an invalid read-only query.",
                            dataset=dataset.id,
                        )
                    )
                try:
                    self.parameter_resolver.schema_for_dataset(dataset)
                except RuntimeParameterError:
                    issues.append(
                        self._issue(
                            "invalid_query_parameter_default",
                            "error",
                            "A query parameter has an invalid configured default.",
                            dataset=dataset.id,
                        )
                    )

        binding_codes = {
            "missing_dataset": "missing_bound_dataset",
            "missing_band_dataset": "missing_bound_dataset",
            "missing_field": "missing_bound_field",
            "band_dataset_mismatch": "band_dataset_conflict",
            "unsupported_object_type": "invalid_binding",
        }
        for binding_issue in self.binding_service.validate(report).issues:
            code = binding_codes.get(binding_issue.code, "invalid_binding")
            issues.append(
                self._issue(
                    code,
                    "error",
                    binding_issue.message,
                    dataset=binding_issue.dataset_id,
                    object_id=binding_issue.object_id,
                )
            )
        if report.datasets:
            issues.append(
                self._issue(
                    "metadata_not_checked", "info", "Dataset field freshness has not been checked."
                )
            )
        blocking = tuple(issue for issue in issues if issue.severity == "error")
        return ReportReopenInspectionResult(not blocking, True, not blocking, tuple(issues))

    @staticmethod
    def _issue(
        code: str,
        severity: str,
        message: str,
        *,
        source: str | None = None,
        dataset: str | None = None,
        object_id: str | None = None,
    ) -> ReportReopenIssue:
        return ReportReopenIssue(code, severity, message, source, dataset, object_id)


class ReportPreviewReadinessService:
    def __init__(self, reopen_service: ReportTemplateReopenService | None = None) -> None:
        self.reopen_service = reopen_service or ReportTemplateReopenService()

    def evaluate(
        self, report: Any, *, dataset_id: str | None = None
    ) -> ReportPreviewReadinessResult:
        inspection = self.reopen_service.inspect(report)
        selected = dataset_id
        issues = list(inspection.issues)
        if report.datasets:
            if selected is None and len(report.datasets) == 1:
                selected = report.datasets[0].id
            elif selected is None:
                issues.append(
                    ReportReopenIssue(
                        "primary_dataset_required", "error", "Select a primary dataset for preview."
                    )
                )
            elif report.get_dataset(selected) is None:
                issues.append(
                    ReportReopenIssue(
                        "missing_dataset",
                        "error",
                        "The selected preview dataset is missing.",
                        dataset_id=selected,
                    )
                )
        relevant = tuple(
            issue
            for issue in issues
            if issue.severity == "error" and (issue.dataset_id in (None, selected))
        )
        return ReportPreviewReadinessResult(not relevant, selected, tuple(issues))


class ReportSaveValidationService:
    def __init__(self, reopen_service: ReportTemplateReopenService | None = None) -> None:
        self.reopen_service = reopen_service or ReportTemplateReopenService()

    def evaluate(self, report: Any) -> ReportSaveValidationResult:
        structural = report.validate()
        structural_errors = tuple(
            ReportReopenIssue(issue.code, "error", issue.message) for issue in structural.errors
        )
        security = inspect_template_security(_unsafe_report_mapping(report))
        security_errors = tuple(
            ReportReopenIssue(
                "unsafe_persisted_field", "error", f"Unsafe persisted field found at {path}."
            )
            for path in security.issues
        )
        inspection = self.reopen_service.inspect(report)
        relationship_codes = {
            "unsupported_provider",
            "invalid_data_source",
            "missing_dataset_data_source",
        }
        relationship_errors = tuple(
            issue for issue in inspection.issues if issue.code in relationship_codes
        )
        runtime_warnings = tuple(
            ReportReopenIssue(
                issue.code,
                "warning",
                issue.message,
                issue.data_source_id,
                issue.dataset_id,
                issue.object_id,
            )
            for issue in inspection.issues
            if issue.severity == "error" and issue.code not in relationship_codes
        )
        errors = structural_errors + relationship_errors + security_errors
        return ReportSaveValidationResult(
            not errors,
            not (structural_errors or relationship_errors),
            inspection.can_preview,
            errors,
            runtime_warnings,
        )


def credential_resolution_status(
    data_source: ReportDataSource,
    resolver: CredentialResolver | None = None,
) -> CredentialResolutionStatus:
    config = data_source.connection
    if config.password is not None:
        return CredentialResolutionStatus(True, True, "runtime", "Runtime credential available.")
    if config.password_ref is None:
        return CredentialResolutionStatus(False, True, "none", "No password is configured.")
    if resolver is not None:
        try:
            if _call_resolver(resolver, config.password_ref, data_source=data_source) is not None:
                source = getattr(resolver, "source_label", "host")
                return CredentialResolutionStatus(
                    True, True, source, "Credential reference resolved."
                )
        except Exception:
            return CredentialResolutionStatus(
                True, False, None, "Credential could not be resolved."
            )
    try:
        if (
            EnvironmentCredentialResolver().resolve(config.password_ref, data_source=data_source)
            is not None
        ):
            return CredentialResolutionStatus(
                True, True, "environment", "Environment credential available."
            )
    except ValueError:
        pass
    return CredentialResolutionStatus(True, False, None, "Credential could not be resolved.")


def _unsafe_report_mapping(report: Any) -> dict[str, Any]:
    """Build a diagnostic mapping that deliberately includes in-model passwords."""
    from .serialization import JSONSerializer

    mapping = JSONSerializer().dump_mapping(report, inspect_security=False)
    for index, source in enumerate(report.data_sources):
        if source.connection.password is not None:
            mapping["dataSources"][index]["connection"]["password"] = "<runtime>"
    return mapping


def _call_resolver(
    resolver: CredentialResolver,
    reference: str,
    *,
    data_source: ReportDataSource | None,
) -> str | None:
    try:
        return resolver.resolve(reference, data_source=data_source)
    except TypeError as exc:
        try:
            return resolver.resolve(reference)  # type: ignore[call-arg]
        except TypeError:
            raise exc from None


def _major_version(value: str) -> int:
    try:
        return int(value.strip().split(".", 1)[0])
    except (TypeError, ValueError):
        raise ReportSerializationError("Report template version is invalid.") from None
