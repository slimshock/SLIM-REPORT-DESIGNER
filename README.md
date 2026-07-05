# Slim Report Designer

Slim Report Designer is an open-source, framework-agnostic reporting platform for Python applications. It provides a JSON-based report engine, pluggable widgets, multiple exporters, and framework adapters starting with Flask.

## Current Status

The project is in early alpha. The current working flow supports loading a JSON report template, resolving data fields, previewing as HTML, and exporting as PDF.

Implemented now:

- Framework-agnostic `slim_report_core`
- Pure Python rendering API
- HTML preview renderer
- ReportLab PDF renderer
- Text, field, line, and rectangle objects
- Flask adapter with template storage, provider registration, preview, PDF export, and a simple JSON designer page
- CLI commands for validation, inspection, and rendering

Not implemented in this stabilization sprint:

- Tables
- Barcode or QR rendering
- Images
- Designer drag and drop
- Pagination

## Architecture Rules

`slim_report_core` must never import Flask, Django, FastAPI, SQLAlchemy, or any web framework.

Rendering belongs in `slim_report_core`. Framework adapters such as `slim_report_flask` should only handle framework concerns: routes, requests, responses, provider registration, storage orchestration, and calling the core.

## Packages

- `slim_report_core`: report models, expression resolution, rendering, widgets, exporters, and pure Python API
- `slim_report_flask`: Flask extension, blueprint routes, template storage, and provider registration
- `slim_report_cli`: command-line interface using only `slim_report_core`
- `slim_report_django`: future Django adapter placeholder
- `slim_report_fastapi`: future FastAPI adapter placeholder

## Pure Python Rendering

```python
from slim_report_core import Report, render_html, render_pdf

template_json = {
    "version": "1.0",
    "metadata": {"title": "Example", "custom": {}},
    "page": {"size": "letter", "orientation": "portrait", "unit": "px"},
    "objects": [
        {
            "id": "patient_name",
            "type": "field",
            "x": 50,
            "y": 90,
            "width": 300,
            "height": 20,
            "binding": "patient.name",
            "style": {"font_size": 12},
        }
    ],
    "bands": [],
    "assets": [],
}

data = {"patient": {"name": "JUAN DELA CRUZ"}}

html = render_html(template_json, data)
pdf_bytes = render_pdf(template_json, data)

report = Report.load_from_dict(template_json)
html = report.render_html(data)
pdf_bytes = report.render_pdf(data)
```

Missing fields render as an empty string.

## Flask Example

Install the local packages in editable mode:

```bash
python -m pip install -e packages/slim_report_core
python -m pip install -e packages/slim_report_flask
```

Run the demo app:

```bash
python examples/flask_app/app.py
```

Open these routes:

```text
http://127.0.0.1:5000/report-designer/templates/lab_result/designer
http://127.0.0.1:5000/report-designer/templates/lab_result/preview/sample
http://127.0.0.1:5000/report-designer/templates/lab_result/export/pdf/sample
```

The demo provider is defined in `examples/flask_app/app.py`, and the sample template is in `examples/flask_app/sample_templates/lab_result.json`.

## CLI

```bash
slim-report validate examples/flask_app/sample_templates/lab_result.json
slim-report inspect examples/flask_app/sample_templates/lab_result.json
slim-report render examples/flask_app/sample_templates/lab_result.json data.json output.html --format html
slim-report render examples/flask_app/sample_templates/lab_result.json data.json output.pdf
```

## Development

This repository uses a Python `src/` layout for each package and shared tool configuration in the root `pyproject.toml`.

```bash
python -m pip install -e packages/slim_report_core
python -m pip install -e packages/slim_report_flask
python -m pip install -e packages/slim_report_cli
python -m pip install pytest ruff
python -m pytest
python -m ruff check packages tests
```

## Repository Layout

```text
packages/
  slim_report_core/
  slim_report_flask/
  slim_report_django/
  slim_report_fastapi/
  slim_report_cli/
examples/
  pure_python/
  flask_app/
  django_app/
  fastapi_app/
  lis_demo/
  pos_demo/
docs/
tests/
scripts/
```
