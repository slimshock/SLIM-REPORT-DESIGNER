from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from slim_report_core.storage import (
    DBAPITemplateProvider,
    FileSystemTemplateProvider,
    PyMySQLTemplateProvider,
    SQLAlchemyTemplateProvider,
    TemplateIdError,
    TemplateNotFoundError,
    TemplatePermissionError,
    TemplateProvider,
    TemplateStorageError,
    TemplateValidationError,
    validate_template_id,
)


def simple_template(name: str = "Storage Template") -> dict[str, Any]:
    return {
        "version": "1.0",
        "metadata": {"name": name, "description": "Storage smoke"},
        "page": {"width": 300, "height": 200, "unit": "px"},
        "objects": [
            {
                "id": "title",
                "type": "text",
                "x": 10,
                "y": 10,
                "width": 180,
                "height": 20,
                "text": "Hello {{ patient.name }}",
            }
        ],
        "bands": [],
        "assets": [],
        "data": {"sample": {"patient": {"name": "Sample Patient"}}},
    }


def test_storage_public_imports() -> None:
    assert TemplateProvider is not None
    assert FileSystemTemplateProvider is not None
    assert DBAPITemplateProvider is not None
    assert PyMySQLTemplateProvider is not None
    assert SQLAlchemyTemplateProvider is not None
    assert TemplateNotFoundError is not None


def test_template_id_validation_allows_safe_ids() -> None:
    for template_id in [
        "lab_result",
        "complete_sprint5_lab_report",
        "receipt-v1",
        "hematology.result",
    ]:
        assert validate_template_id(template_id) == template_id


def test_template_id_validation_rejects_unsafe_ids() -> None:
    for template_id in [
        "../secret",
        "../../app.py",
        r"C:\secret",
        "folder/template",
        "template.json/other",
        "",
    ]:
        with pytest.raises(TemplateIdError):
            validate_template_id(template_id)


def test_filesystem_template_provider_crud_and_permissions(tmp_path: Path) -> None:
    provider = FileSystemTemplateProvider(tmp_path, allow_save=True)
    ignored = tmp_path / "ignored.txt"
    ignored.write_text("not json", encoding="utf-8")

    saved = provider.save_template("lab_result", simple_template())
    templates = provider.list_templates()
    loaded = provider.get_template("lab_result")

    assert saved["metadata"]["title"] == "Storage Template"
    assert [item["id"] for item in templates] == ["lab_result"]
    assert loaded["metadata"]["title"] == "Storage Template"
    assert provider.get_sample_data("lab_result")["patient"]["name"] == "Sample Patient"
    assert provider.exists("lab_result")
    assert not provider.exists("../secret")
    with pytest.raises(TemplateNotFoundError):
        provider.get_template("missing")
    with pytest.raises(TemplateIdError):
        provider.get_template("../secret")
    with pytest.raises(TemplatePermissionError):
        provider.delete_template("lab_result")

    deleting_provider = FileSystemTemplateProvider(tmp_path, allow_save=True, allow_delete=True)
    assert deleting_provider.delete_template("lab_result") is True
    assert not deleting_provider.exists("lab_result")


def test_filesystem_template_provider_blocks_save_by_default(tmp_path: Path) -> None:
    provider = FileSystemTemplateProvider(tmp_path)

    with pytest.raises(TemplatePermissionError):
        provider.save_template("lab_result", simple_template())


def test_sqlalchemy_template_provider_crud_and_soft_delete() -> None:
    pytest.importorskip("sqlalchemy")
    session, model = sqlalchemy_session_and_model()
    provider = SQLAlchemyTemplateProvider(session, model, allow_save=True, allow_delete=True)

    saved = provider.save_template("lab_result", simple_template())
    updated = provider.save_template("lab_result", simple_template("Updated Template"))
    templates = provider.list_templates()
    loaded = provider.get_template("lab_result")

    assert saved["metadata"]["title"] == "Storage Template"
    assert updated["metadata"]["title"] == "Updated Template"
    assert templates[0]["id"] == "lab_result"
    assert templates[0]["name"] == "Updated Template"
    assert templates[0]["version"] == 2
    assert loaded["data"]["sample"]["patient"]["name"] == "Sample Patient"
    assert provider.exists("lab_result")
    assert provider.delete_template("lab_result") is True
    assert not provider.exists("lab_result")
    assert provider.list_templates() == []

    revived = provider.save_template("lab_result", simple_template("Revived Template"))

    assert revived["metadata"]["title"] == "Revived Template"
    assert provider.exists("lab_result")
    assert provider.list_templates()[0]["version"] == 3


def test_sqlalchemy_template_provider_text_json_fields() -> None:
    pytest.importorskip("sqlalchemy")
    session, model = sqlalchemy_session_and_model(text_fields=True)
    provider = SQLAlchemyTemplateProvider(
        session,
        model,
        template_field="template_json_text",
        sample_data_field="sample_data_json_text",
        allow_save=True,
        json_dumps=json.dumps,
        json_loads=json.loads,
    )

    provider.save_template("lab_result", simple_template())
    loaded = provider.get_template("lab_result")

    assert loaded["metadata"]["title"] == "Storage Template"
    assert loaded["data"]["sample"]["patient"]["name"] == "Sample Patient"


def test_sqlalchemy_template_provider_clean_errors() -> None:
    pytest.importorskip("sqlalchemy")
    session, model = sqlalchemy_session_and_model()
    readonly = SQLAlchemyTemplateProvider(session, model, allow_save=False)

    with pytest.raises(TemplatePermissionError):
        readonly.save_template("lab_result", simple_template())

    provider = SQLAlchemyTemplateProvider(session, model, allow_save=True)
    with pytest.raises(TemplateNotFoundError):
        provider.get_template("missing")
    with pytest.raises(TemplateIdError):
        provider.get_template("../secret")


def test_pymysql_template_provider_crud_and_soft_delete() -> None:
    connection = FakeDBAPIConnection()
    provider = PyMySQLTemplateProvider(
        lambda: connection,
        allow_save=True,
        allow_delete=True,
    )

    provider.ensure_schema()
    saved = provider.save_template("lab_result", simple_template())
    updated = provider.save_template("lab_result", simple_template("Updated Template"))
    templates = provider.list_templates()
    loaded = provider.get_template("lab_result")

    assert connection.schema_created
    assert connection.ping_count >= 1
    assert saved["metadata"]["title"] == "Storage Template"
    assert updated["metadata"]["title"] == "Updated Template"
    assert templates[0]["id"] == "lab_result"
    assert templates[0]["name"] == "Updated Template"
    assert templates[0]["version"] == 2
    assert loaded["data"]["sample"]["patient"]["name"] == "Sample Patient"
    assert provider.get_sample_data("lab_result")["patient"]["name"] == "Sample Patient"
    assert provider.exists("lab_result")
    assert provider.delete_template("lab_result") is True
    assert not provider.exists("lab_result")
    assert provider.list_templates() == []

    revived = provider.save_template("lab_result", simple_template("Revived Template"))

    assert revived["metadata"]["title"] == "Revived Template"
    assert provider.exists("lab_result")
    assert provider.list_templates()[0]["version"] == 3


def test_pymysql_template_provider_permissions_and_clean_errors() -> None:
    connection = FakeDBAPIConnection()
    readonly = PyMySQLTemplateProvider(lambda: connection)

    with pytest.raises(TemplatePermissionError):
        readonly.save_template("lab_result", simple_template())
    with pytest.raises(TemplatePermissionError):
        readonly.delete_template("lab_result")
    with pytest.raises(TemplateNotFoundError):
        readonly.get_template("missing")
    with pytest.raises(TemplateIdError):
        readonly.get_template("../secret")
    with pytest.raises(TemplateIdError):
        readonly.save_template("../secret", simple_template())
    assert not readonly.exists("../secret")

    none_provider = PyMySQLTemplateProvider(lambda: None)
    with pytest.raises(TemplateStorageError, match="Could not connect to MySQL"):
        none_provider.list_templates()

    failing_ping = PyMySQLTemplateProvider(lambda: FakeDBAPIConnection(ping_error=True))
    with pytest.raises(TemplateStorageError, match="Could not connect to MySQL"):
        failing_ping.list_templates()


def test_pymysql_template_provider_schema_sql_validates_table_name() -> None:
    sql = PyMySQLTemplateProvider.create_table_sql("lis.report_templates")

    assert "CREATE TABLE IF NOT EXISTS `lis`.`report_templates`" in sql
    with pytest.raises(TemplateValidationError):
        PyMySQLTemplateProvider(lambda: FakeDBAPIConnection(), table_name="report_templates;drop")


def sqlalchemy_session_and_model(*, text_fields: bool = False):
    from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, Text, create_engine
    from sqlalchemy.orm import declarative_base, sessionmaker

    base = declarative_base()

    class ReportTemplate(base):  # type: ignore[valid-type,misc]
        __tablename__ = "report_templates"

        id = Column(Integer, primary_key=True)
        template_id = Column(String(120), unique=True, nullable=False, index=True)
        name = Column(String(255), nullable=False)
        description = Column(Text, nullable=True)
        category = Column(String(120), nullable=True)
        if text_fields:
            template_json_text = Column(Text, nullable=False)
            sample_data_json_text = Column(Text, nullable=True)
        else:
            template_json = Column(JSON, nullable=False)
            sample_data_json = Column(JSON, nullable=True)
        version = Column(Integer, default=1, nullable=False)
        is_active = Column(Boolean, default=True, nullable=False)
        created_at = Column(DateTime, nullable=True)
        updated_at = Column(DateTime, nullable=True)

    engine = create_engine("sqlite:///:memory:")
    base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    return session, ReportTemplate


class FakeDBAPIConnection:
    def __init__(self, *, ping_error: bool = False) -> None:
        self.rows: dict[str, dict[str, Any]] = {}
        self.ping_error = ping_error
        self.ping_count = 0
        self.commits = 0
        self.rollbacks = 0
        self.schema_created = False

    def ping(self, reconnect: bool = False) -> None:
        self.ping_count += 1
        if self.ping_error:
            raise RuntimeError("stale connection")

    def cursor(self) -> FakeDBAPICursor:
        return FakeDBAPICursor(self)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class FakeDBAPICursor:
    description = (
        ("template_id",),
        ("name",),
        ("description",),
        ("category",),
        ("template_json",),
        ("sample_data_json",),
        ("version",),
        ("is_active",),
        ("created_at",),
        ("updated_at",),
    )

    def __init__(self, connection: FakeDBAPIConnection) -> None:
        self.connection = connection
        self.result: list[dict[str, Any]] = []

    def execute(self, query: str, params: tuple[Any, ...] = ()) -> None:
        normalized = " ".join(query.upper().split())
        if normalized.startswith("CREATE TABLE"):
            self.connection.schema_created = True
            self.result = []
            return
        if normalized.startswith("SELECT") and "WHERE TEMPLATE_ID = %S" in normalized:
            template_id = str(params[0])
            row = self.connection.rows.get(template_id)
            if row and ("AND IS_ACTIVE = 1" not in normalized or row["is_active"]):
                self.result = [dict(row)]
            else:
                self.result = []
            return
        if normalized.startswith("SELECT"):
            self.result = [
                dict(row)
                for row in sorted(
                    self.connection.rows.values(),
                    key=lambda item: (item["name"], item["template_id"]),
                )
                if row["is_active"]
            ]
            return
        if normalized.startswith("INSERT"):
            template_id, name, description, category, template_json, sample_json = params
            self.connection.rows[str(template_id)] = {
                "template_id": template_id,
                "name": name,
                "description": description,
                "category": category,
                "template_json": template_json,
                "sample_data_json": sample_json,
                "version": 1,
                "is_active": True,
                "created_at": "2026-07-09T00:00:00",
                "updated_at": "2026-07-09T00:00:00",
            }
            self.result = []
            return
        if normalized.startswith("UPDATE") and "SET NAME = %S" in normalized:
            name, description, category, template_json, sample_json, template_id = params
            row = self.connection.rows[str(template_id)]
            row.update(
                {
                    "name": name,
                    "description": description,
                    "category": category,
                    "template_json": template_json,
                    "sample_data_json": sample_json,
                    "version": int(row.get("version") or 0) + 1,
                    "is_active": True,
                    "updated_at": "2026-07-09T00:00:01",
                }
            )
            self.result = []
            return
        if normalized.startswith("UPDATE") and "SET IS_ACTIVE = 0" in normalized:
            template_id = str(params[0])
            self.connection.rows[template_id]["is_active"] = False
            self.result = []
            return
        raise AssertionError(f"Unexpected SQL: {query}")

    def fetchone(self) -> dict[str, Any] | None:
        return self.result[0] if self.result else None

    def fetchall(self) -> list[dict[str, Any]]:
        return list(self.result)

    def close(self) -> None:
        return None
