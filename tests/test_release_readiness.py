from __future__ import annotations

import json
import random
import re
from pathlib import Path

import pytest

from slim_report_core import (
    CredentialUnavailableError,
    MySQLDialect,
    SQLValidationError,
    SQLValidator,
)
from slim_report_core.persistence import inspect_template_security
from slim_report_core.serialization import JSONSerializer
from slim_report_core.storage import TemplateStorageError
from slim_report_flask import map_safe_error

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "flask_database_app"


def test_demo_reports_reopen_with_safe_credentials_bindings_and_no_runtime_state() -> None:
    for path in sorted((DEMO / "reports").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        report = JSONSerializer().load_mapping(payload)
        persisted = JSONSerializer().dump_mapping(report)
        inspection = inspect_template_security(persisted)

        assert inspection.safe
        assert report.data_sources
        assert report.datasets
        assert all(source.connection.password is None for source in report.data_sources)
        assert all(source.connection.password_ref for source in report.data_sources)
        assert "rows" not in persisted
        assert "previewHtml" not in persisted
        assert "executionSummary" not in persisted
        assert any(item.dataset_binding is not None for item in report.objects)


def test_demo_sql_is_utf8mb4_view_only_and_restricted_to_explicit_select_grants() -> None:
    schema = (DEMO / "sql" / "sample_schema.sql").read_text(encoding="utf-8")
    views = (DEMO / "sql" / "reporting_views.sql").read_text(encoding="utf-8")
    grants = (DEMO / "sql" / "restricted_user.sql").read_text(encoding="utf-8")

    assert "utf8mb4" in schema
    assert views.count("CREATE OR REPLACE VIEW report_") == 2
    grant_statements = re.findall(r"GRANT\s+.+?;", grants, flags=re.IGNORECASE | re.DOTALL)
    assert len(grant_statements) == 2
    for statement in grant_statements:
        normalized = " ".join(statement.split()).upper()
        assert normalized.startswith("GRANT SELECT ON SLIM_REPORT_DEMO.REPORT_")
        assert ".*" not in statement
        assert not any(
            keyword in normalized
            for keyword in (" INSERT ", " UPDATE ", " DELETE ", " CREATE ", " DROP ", " ALTER ")
        )


def test_demo_uses_installed_imports_and_runtime_execution_never_uses_fetchall() -> None:
    app_source = (DEMO / "app.py").read_text(encoding="utf-8")
    runtime_source = (
        ROOT
        / "packages/slim_report_core/src/slim_report_core/data_source_providers/mysql/execution.py"
    ).read_text(encoding="utf-8")

    assert "sys.path" not in app_source
    assert "PYTHONPATH" not in app_source
    assert "fetchall(" not in runtime_source


@pytest.mark.parametrize(
    "error",
    [
        CredentialUnavailableError("password=release-secret"),
        SQLValidationError("SELECT release-secret FROM private_table"),
        TemplateStorageError("driver failed for release-secret"),
        RuntimeError("unexpected release-secret"),
    ],
)
def test_safe_error_mapping_is_deterministic_and_never_copies_exception_content(
    error: Exception,
) -> None:
    first = map_safe_error(error)
    second = map_safe_error(error)
    serialized = json.dumps(first.to_dict())

    assert first == second
    assert first.code
    assert first.status in {400, 404, 409, 500, 503, 504}
    assert "release-secret" not in serialized
    assert "SELECT" not in serialized
    assert "RuntimeError" not in serialized
    assert first.to_dict()["details"] == []


def test_seeded_sql_robustness_rejects_mutated_unsafe_constructs() -> None:
    randomizer = random.Random(7152026)
    validator = SQLValidator(MySQLDialect())
    unsafe_fragments = [
        "; DELETE FROM patients",
        " FOR UPDATE",
        " INTO OUTFILE '/tmp/result'",
        " WHERE SLEEP(1)",
        " WHERE id = @patient_id",
        " WHERE id = @@server_id",
        " WHERE @patient_id := 1",
    ]
    candidates = [
        "SELECT order_id FROM report_daily_orders" + randomizer.choice(unsafe_fragments)
        for _ in range(100)
    ]

    for candidate in candidates:
        with pytest.raises(SQLValidationError):
            validator.validate(candidate)
