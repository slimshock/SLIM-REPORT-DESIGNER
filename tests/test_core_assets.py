from __future__ import annotations

from pathlib import Path

import pytest

from slim_report_core.assets import (
    AssetIdError,
    AssetNotFoundError,
    AssetPermissionError,
    AssetProvider,
    AssetTypeError,
    FileSystemAssetProvider,
    validate_asset_id,
)


def test_core_asset_public_imports() -> None:
    assert AssetProvider is not None
    assert FileSystemAssetProvider is not None
    assert AssetNotFoundError is not None


@pytest.mark.parametrize(
    "asset_id",
    [
        "clinic_logo",
        "medtech_signature",
        "pathologist_signature",
        "header-logo-v1",
        "watermark.default",
    ],
)
def test_validate_asset_id_accepts_safe_ids(asset_id: str) -> None:
    assert validate_asset_id(asset_id) == asset_id


@pytest.mark.parametrize(
    "asset_id",
    ["../secret", "../../app.py", r"C:\secret", "folder/image", "image.png/other", ""],
)
def test_validate_asset_id_rejects_unsafe_ids(asset_id: str) -> None:
    with pytest.raises(AssetIdError):
        validate_asset_id(asset_id)


def test_filesystem_asset_provider_lists_gets_opens_and_returns_url(tmp_path: Path) -> None:
    (tmp_path / "clinic_logo.svg").write_text("<svg></svg>", encoding="utf-8")
    provider = FileSystemAssetProvider(tmp_path, base_url="/report-designer/assets")

    assets = provider.list_assets()
    metadata = provider.get_asset("clinic_logo")

    assert assets[0]["id"] == "clinic_logo"
    assert metadata["filename"] == "clinic_logo.svg"
    assert metadata["content_type"] == "image/svg+xml"
    assert metadata["url"] == "/report-designer/assets/clinic_logo"
    assert provider.get_asset_url("clinic_logo") == "/report-designer/assets/clinic_logo"
    with provider.open_asset("clinic_logo") as asset_file:
        assert asset_file.read() == b"<svg></svg>"


def test_filesystem_asset_provider_save_requires_explicit_enable(tmp_path: Path) -> None:
    provider = FileSystemAssetProvider(tmp_path)

    with pytest.raises(AssetPermissionError):
        provider.save_asset("clinic_logo", b"<svg></svg>", content_type="image/svg+xml")


def test_filesystem_asset_provider_save_and_delete_when_allowed(tmp_path: Path) -> None:
    provider = FileSystemAssetProvider(
        tmp_path,
        allow_save=True,
        allow_delete=True,
    )

    saved = provider.save_asset("clinic_logo", b"<svg></svg>", content_type="image/svg+xml")
    deleted = provider.delete_asset("clinic_logo")

    assert saved["id"] == "clinic_logo"
    assert (tmp_path / "clinic_logo.svg").exists() is False
    assert deleted is True


def test_filesystem_asset_provider_blocks_delete_by_default(tmp_path: Path) -> None:
    (tmp_path / "clinic_logo.svg").write_text("<svg></svg>", encoding="utf-8")
    provider = FileSystemAssetProvider(tmp_path)

    with pytest.raises(AssetPermissionError):
        provider.delete_asset("clinic_logo")


def test_filesystem_asset_provider_rejects_invalid_and_unsupported_paths(tmp_path: Path) -> None:
    provider = FileSystemAssetProvider(tmp_path, allow_save=True)

    assert not provider.exists("../secret")
    with pytest.raises(AssetIdError):
        provider.get_asset("../secret")
    with pytest.raises(AssetTypeError):
        provider.save_asset("script.exe", b"bad", content_type="application/octet-stream")
