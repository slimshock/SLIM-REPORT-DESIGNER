from __future__ import annotations

from pathlib import Path

from slim_report_core import render_html, render_pdf
from slim_report_core.serialization import JSONSerializer

REPO_ROOT = Path(__file__).resolve().parents[1]
LIS_TEMPLATE_DIR = REPO_ROOT / "examples" / "lis_templates"


def test_lis_sample_templates_load_and_render() -> None:
    serializer = JSONSerializer()
    paths = sorted(LIS_TEMPLATE_DIR.glob("*.json"))

    assert {path.name for path in paths} == {
        "lab_result_hematology.json",
        "lab_result_hematology_two_column.json",
    }

    for path in paths:
        report = serializer.load(path)
        data = dict(getattr(report, "data", {}).get("sample", {}))
        html = render_html(report, data)
        pdf = render_pdf(report, data)

        assert report.metadata.title
        assert "Juan Dela Cruz" in html
        assert ">Image<" not in html
        assert pdf.startswith(b"%PDF")
        assert len(pdf) > 100
