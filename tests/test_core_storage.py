from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from slim_report_core.storage import (
    FileSystemTemplateProvider,
    SQLAlchemyTemplateProvider,
    TemplateIdError,
    TemplateNotFoundError,
    TemplatePermissionError,
    TemplateProvider,
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


def sqlalchemy_session_and_model(*, text_fields: bool = False):
    from sqlalchemy import Boolean, Column, DateTime, Integer, JSON, String, Text, create_engine
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
