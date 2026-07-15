from __future__ import annotations

import copy

import pytest

from slim_report_core import (
    CompositeCredentialResolver,
    CredentialPersistencePolicy,
    DatasetField,
    DatasetFreshnessService,
    DatasetSourceType,
    MySQLConnectionConfig,
    Report,
    ReportDataset,
    ReportDataSource,
    ReportPreviewReadinessService,
    ReportSaveValidationService,
    ReportTemplateReopenService,
    create_persistable_report_snapshot,
    inspect_template_security,
)
from slim_report_core.exceptions import ReportSerializationError
from slim_report_core.serialization import JSONSerializer


def template_mapping() -> dict:
    return {
        "version": "1.0",
        "metadata": {"title": "Persistence"},
        "page": {"width": 595, "height": 842, "unit": "px"},
        "objects": [],
        "bands": [],
        "assets": [],
        "dataSources": [
            {
                "id": "mysql",
                "name": "Main MySQL",
                "type": "mysql",
                "connection": {
                    "host": "localhost",
                    "database": "lis",
                    "username": "reader",
                    "passwordRef": "TEST_REPORT_PASSWORD",
                },
            }
        ],
        "datasets": [
            {
                "id": "results",
                "name": "Results",
                "dataSourceId": "mysql",
                "sourceType": "view",
                "viewName": "report_results",
                "fields": [{"name": "id", "dataType": "integer", "nullable": False}],
            }
        ],
    }


def test_legacy_plaintext_password_is_removed_and_reported() -> None:
    mapping = template_mapping()
    mapping["dataSources"][0]["connection"]["password"] = "never-persist"

    report = JSONSerializer().load_mapping(mapping)
    dumped = JSONSerializer().dump_mapping(report)

    assert report.data_sources[0].connection.password is None
    assert "password" not in dumped["dataSources"][0]["connection"]
    assert report._reopen_migration_issues[0].code == "legacy_plaintext_password_removed"


def test_future_major_template_fails_before_partial_load() -> None:
    mapping = template_mapping()
    mapping["version"] = "2.0"

    with pytest.raises(ReportSerializationError, match="newer version"):
        JSONSerializer().load_mapping(mapping)


def test_security_inspection_returns_paths_only() -> None:
    result = inspect_template_security(
        {"dataSources": [{"connection": {"password": "secret"}}], "previewHtml": "x"}
    )

    assert not result.safe
    assert result.issues == (
        "dataSources[0].connection.password",
        "previewHtml",
    )
    assert "secret" not in repr(result)


def test_persistable_snapshot_strips_password_without_mutating_original() -> None:
    report = JSONSerializer().load_mapping(template_mapping())
    report.data_sources[0].connection.password = "runtime-only"

    snapshot = create_persistable_report_snapshot(report)

    assert report.data_sources[0].connection.password == "runtime-only"
    assert snapshot.data_sources[0].connection.password is None
    assert snapshot.data_sources[0].connection.password_ref == "TEST_REPORT_PASSWORD"
    assert "runtime-only" not in repr(report.data_sources[0].connection)


def test_composite_resolver_stops_after_first_success() -> None:
    calls: list[str] = []

    class Resolver:
        def __init__(self, value: str | None) -> None:
            self.value = value

        def resolve(self, reference: str, *, data_source: object = None) -> str | None:
            del data_source
            calls.append(reference)
            return self.value

    resolver = CompositeCredentialResolver((Resolver("resolved"), Resolver("late")))

    assert resolver.resolve("REFERENCE") == "resolved"
    assert calls == ["REFERENCE"]


def test_reopen_and_readiness_are_non_mutating_and_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TEST_REPORT_PASSWORD", raising=False)
    report = JSONSerializer().load_mapping(template_mapping())
    before = JSONSerializer().dump_mapping(report)

    inspection = ReportTemplateReopenService().inspect(report)
    readiness = ReportPreviewReadinessService().evaluate(report, dataset_id="results")

    assert inspection.can_edit
    assert not inspection.can_preview
    assert not readiness.ready
    assert "credential_unresolved" in {issue.code for issue in inspection.issues}
    assert JSONSerializer().dump_mapping(report) == before


def test_save_allows_runtime_warning_but_blocks_in_model_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TEST_REPORT_PASSWORD", raising=False)
    report = JSONSerializer().load_mapping(template_mapping())

    warning_result = ReportSaveValidationService().evaluate(report)
    report.data_sources[0].connection.password = "runtime-only"
    blocked_result = ReportSaveValidationService().evaluate(report)

    assert warning_result.can_save
    assert not warning_result.runtime_ready
    assert warning_result.warnings
    assert not blocked_result.can_save
    assert blocked_result.errors[0].code == "unsafe_persisted_field"


def test_dataset_freshness_compares_without_mutating_report() -> None:
    report = JSONSerializer().load_mapping(template_mapping())
    before = copy.deepcopy(report.datasets[0].to_dict())

    result = DatasetFreshnessService().compare(
        report,
        "results",
        (
            DatasetField("id", "integer", True),
            DatasetField("name", "string", True),
        ),
    )

    assert not result.fresh
    assert result.added_fields == ("name",)
    assert result.changed_fields == ("id",)
    assert report.datasets[0].to_dict() == before


def test_policy_rejects_non_boolean_and_plaintext_serialization_mode() -> None:
    with pytest.raises(TypeError):
        CredentialPersistencePolicy(allow_password_reference=1)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        CredentialPersistencePolicy(allow_runtime_password_serialization=True)


def test_missing_dataset_relationship_remains_inspectable() -> None:
    report = Report()
    report.datasets.append(
        ReportDataset(
            id="orphan",
            name="Orphan",
            data_source_id="missing",
            source_type=DatasetSourceType.VIEW,
            view_name="report_orphan",
            fields=[DatasetField("id")],
        )
    )

    result = ReportTemplateReopenService().inspect(report)

    assert result.can_edit
    assert not result.can_preview
    assert "missing_dataset_data_source" in {issue.code for issue in result.issues}


def test_no_password_configuration_is_explicitly_supported() -> None:
    report = Report(
        data_sources=[
            ReportDataSource(
                id="mysql",
                name="Local",
                connection=MySQLConnectionConfig(
                    host="localhost", database="lis", username="reader"
                ),
            )
        ]
    )

    assert ReportTemplateReopenService().inspect(report).can_preview
