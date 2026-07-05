"""Create a simple report and save it as JSON."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CORE_SRC = REPO_ROOT / "packages" / "slim_report_core" / "src"
if str(CORE_SRC) not in sys.path:
    sys.path.insert(0, str(CORE_SRC))

from slim_report_core import Report, ReportObject


def main() -> None:
    report = Report()
    report.template.metadata.title = "Pure Python Report"
    report.template.metadata.description = "A minimal report created without a web framework."

    report.add_object(
        ReportObject(
            id="title",
            type="text",
            x=0.5,
            y=0.5,
            width=7.5,
            height=0.4,
            properties={
                "text": "Hello from Slim Report Designer",
                "font_size": 18,
                "font_weight": "bold",
            },
        )
    )

    output_path = Path(__file__).with_name("report.json")
    output_path.write_text(report.to_json(), encoding="utf-8")
    print(f"Saved {output_path}")


if __name__ == "__main__":
    main()
