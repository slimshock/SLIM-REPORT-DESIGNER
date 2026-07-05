"""Command-line interface for Slim Report Designer."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from slim_report_core import ExporterError, Report, SlimReportError


def main(argv: Sequence[str] | None = None) -> int:
    """Run the slim-report command-line interface."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return args.handler(args)
    except (OSError, json.JSONDecodeError, SlimReportError) as exc:
        print(f"slim-report: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(
        prog="slim-report",
        description="Render, validate, and inspect Slim Report Designer templates.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    render_parser = subparsers.add_parser("render", help="Render a report template.")
    render_parser.add_argument("template", help="Path to the report template JSON file.")
    render_parser.add_argument("data", help="Path to the input data JSON file.")
    render_parser.add_argument("output", help="Path to the rendered output file.")
    render_parser.add_argument(
        "--format",
        choices=["html", "pdf"],
        help="Output format. Defaults to the output file extension.",
    )
    render_parser.set_defaults(handler=render_command)

    validate_parser = subparsers.add_parser("validate", help="Validate a report template.")
    validate_parser.add_argument("template", help="Path to the report template JSON file.")
    validate_parser.set_defaults(handler=validate_command)

    inspect_parser = subparsers.add_parser("inspect", help="Inspect a report template.")
    inspect_parser.add_argument("template", help="Path to the report template JSON file.")
    inspect_parser.set_defaults(handler=inspect_command)

    return parser


def render_command(args: argparse.Namespace) -> int:
    """Render a template with a JSON data file."""
    report = Report.load_json(args.template)
    data = load_data(args.data)
    output_path = Path(args.output)
    output_format = args.format or infer_format(output_path)

    rendered = report.render(data, exporter=output_format)
    if output_format == "pdf":
        if not isinstance(rendered, bytes):
            raise ExporterError("PDF exporter must return bytes.")
        output_path.write_bytes(rendered)
    else:
        if isinstance(rendered, bytes):
            rendered = rendered.decode("utf-8")
        output_path.write_text(rendered, encoding="utf-8")

    print(f"Rendered {output_format} report: {output_path}")
    return 0


def validate_command(args: argparse.Namespace) -> int:
    """Validate a template by loading it into the core report model."""
    Report.load_json(args.template)
    print(f"Valid report template: {args.template}")
    return 0


def inspect_command(args: argparse.Namespace) -> int:
    """Print a compact report template summary."""
    report = Report.load_json(args.template)
    template = report.template
    object_types = sorted({obj.type for obj in template.objects})

    print(f"Title: {template.metadata.title}")
    print(f"Version: {template.version}")
    print(
        "Page: "
        f"{template.page.width:g} x {template.page.height:g} "
        f"{template.page.unit} {template.page.orientation}"
    )
    print(f"Objects: {len(template.objects)}")
    print(f"Bands: {len(template.bands)}")
    print(f"Assets: {len(template.assets)}")
    print(f"Object types: {', '.join(object_types) if object_types else 'none'}")
    return 0


def load_data(path: str) -> Any:
    """Load render data from JSON."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def infer_format(output_path: Path) -> str:
    """Infer render format from output file extension."""
    suffix = output_path.suffix.lower()
    if suffix in {".html", ".htm"}:
        return "html"
    if suffix == ".pdf":
        return "pdf"
    raise ExporterError(
        f"Cannot infer output format from extension {suffix!r}. Use --format html or --format pdf."
    )
