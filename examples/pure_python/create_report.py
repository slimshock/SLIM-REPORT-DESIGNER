"""Create and render a simple report without a web framework."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CORE_SRC = REPO_ROOT / "packages" / "slim_report_core" / "src"
if str(CORE_SRC) not in sys.path:
    sys.path.insert(0, str(CORE_SRC))

from slim_report_core import Report, ReportObject  # noqa: E402
from slim_report_core.serialization import JSONSerializer  # noqa: E402


def main() -> None:
    """Create a template, render HTML, and render PDF bytes."""
    report = Report()
    report.metadata.title = "Pure Python Report"
    report.metadata.description = "A minimal report created without a web framework."
    report.page.width = 816
    report.page.height = 1056
    report.page.unit = "px"

    report.add_object(
        ReportObject(
            id="title",
            type="text",
            x=50,
            y=40,
            width=500,
            height=32,
            properties={
                "text": "PURE PYTHON REPORT",
                "style": {"font_size": 22, "bold": True},
            },
        )
    )
    report.add_object(
        ReportObject(
            id="patient_name",
            type="field",
            x=50,
            y=90,
            width=300,
            height=22,
            properties={
                "binding": "patient.name",
                "style": {"font_size": 13},
            },
        )
    )

    data = {"patient": {"name": "JUAN DELA CRUZ"}}
    output_dir = Path(__file__).resolve().parent
    JSONSerializer().save(report, output_dir / "report.json")
    (output_dir / "report.html").write_text(report.render_html(data), encoding="utf-8")
    (output_dir / "report.pdf").write_bytes(report.render_pdf(data))
    print(f"Saved report outputs in {output_dir}")


if __name__ == "__main__":
    main()
