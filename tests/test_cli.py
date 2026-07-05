from __future__ import annotations

from pathlib import Path

from slim_report_cli import main
from slim_report_core import Report, ReportObject


def test_cli_validate_template(tmp_path: Path, capsys) -> None:
    template_path = write_template(tmp_path)

    exit_code = main(["validate", str(template_path)])

    assert exit_code == 0
    assert "Valid report template" in capsys.readouterr().out


def test_cli_inspect_template(tmp_path: Path, capsys) -> None:
    template_path = write_template(tmp_path)

    exit_code = main(["inspect", str(template_path)])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Title: CLI Report" in output
    assert "Objects: 1" in output
    assert "Object types: text" in output


def test_cli_render_html_with_explicit_format(tmp_path: Path, capsys) -> None:
    template_path = write_template(tmp_path)
    data_path = tmp_path / "data.json"
    output_path = tmp_path / "output.html"
    data_path.write_text('{"patient": {"name": "Lara"}}', encoding="utf-8")

    exit_code = main(
        [
            "render",
            str(template_path),
            str(data_path),
            str(output_path),
            "--format",
            "html",
        ]
    )

    assert exit_code == 0
    assert "Rendered html report" in capsys.readouterr().out
    assert "Patient: Lara" in output_path.read_text(encoding="utf-8")


def test_cli_render_html_by_extension(tmp_path: Path) -> None:
    template_path = write_template(tmp_path)
    data_path = tmp_path / "data.json"
    output_path = tmp_path / "output.html"
    data_path.write_text('{"patient": {"name": "Mira"}}', encoding="utf-8")

    exit_code = main(["render", str(template_path), str(data_path), str(output_path)])

    assert exit_code == 0
    assert "Patient: Mira" in output_path.read_text(encoding="utf-8")


def test_cli_render_rejects_unknown_extension(tmp_path: Path, capsys) -> None:
    template_path = write_template(tmp_path)
    data_path = tmp_path / "data.json"
    data_path.write_text("{}", encoding="utf-8")

    exit_code = main(["render", str(template_path), str(data_path), str(tmp_path / "out.txt")])

    assert exit_code == 1
    assert "Cannot infer output format" in capsys.readouterr().err


def write_template(tmp_path: Path) -> Path:
    report = Report()
    report.template.metadata.title = "CLI Report"
    report.add_object(
        ReportObject(
            id="title",
            type="text",
            width=3,
            height=0.5,
            properties={"text": "Patient: {{ patient.name }}"},
        )
    )
    template_path = tmp_path / "template.json"
    report.save_json(template_path)
    return template_path
