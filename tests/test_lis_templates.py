from __future__ import annotations

from pathlib import Path

from slim_report_core import render_html, render_pdf
from slim_report_core.assets import FileSystemAssetProvider
from slim_report_core.serialization import JSONSerializer

REPO_ROOT = Path(__file__).resolve().parents[1]
LIS_TEMPLATE_DIR = REPO_ROOT / "examples" / "lis_templates"


def test_lis_sample_templates_load_and_render() -> None:
    serializer = JSONSerializer()
    paths = sorted(LIS_TEMPLATE_DIR.glob("*.json"))

    assert {path.name for path in paths} == {
        "lab_result_hematology_assets.json",
        "lab_result_hematology.json",
        "lab_result_hematology_two_column.json",
    }

    asset_provider = FileSystemAssetProvider(
        REPO_ROOT / "examples" / "assets",
        base_url="/report-designer/assets",
    )
    for path in paths:
        report = serializer.load(path)
        data = dict(getattr(report, "data", {}).get("sample", {}))
        html = render_html(report, data, asset_provider=asset_provider)
        pdf = render_pdf(report, data, asset_provider=asset_provider)

        assert report.metadata.title
        assert "Juan Dela Cruz" in html
        assert ">Image<" not in html
        assert pdf.startswith(b"%PDF")
        assert len(pdf) > 100

        if path.name == "lab_result_hematology_assets.json":
            assert "/report-designer/assets/clinic_logo" in html
            assert "/report-designer/assets/pathologist_signature" in html
            assert 'data-slim-object="empty_signature_slot"' in html
        if path.name == "lab_result_hematology_two_column.json":
            assert 'data-slim-object="left_table"' in html
            assert 'data-slim-object="right_table"' in html
            assert "Hemoglobin" in html
            assert "HIGH" in html
            assert "LOW" in html
            assert "Red Cell Indices" in html
            assert "slim-report-table-section-row" in html
            assert "background: #fee2e2" in html
            assert "background: #dbeafe" in html
