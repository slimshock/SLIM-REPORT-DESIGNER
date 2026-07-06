# Slim Report Designer

Slim Report Designer is an early-alpha, framework-agnostic Python report designer and rendering toolkit.

It includes:

- Python Report API
- JSON template serialization
- HTML preview
- PDF export
- Static visual designer UI
- Flask integration
- Future adapters for Django and FastAPI

The designer UI is plain HTML, CSS, and JavaScript. It has no React, no Vue, no npm build step, and no frontend framework dependency.

The project is not production-ready yet. Contributions, issues, and feedback are welcome while the public API and template format continue to mature.

Suggested repository description:

```text
Framework-agnostic Python report designer with visual canvas, JSON templates, HTML preview, and PDF export.
```

Suggested topics:

```text
python, reporting, report-designer, pdf-generation, flask, reportlab, json-template, drag-and-drop, html-preview, open-source
```

## Current Status

Implemented now:

- Framework-agnostic `slim_report_core`
- Report-first Python API
- JSON template serialization through `JSONSerializer`
- HTML preview renderer
- ReportLab PDF renderer
- Text, field, line, rectangle, and image objects
- Visual designer canvas
- Drag and drop
- Resize handles
- Inspector and style inspector
- Page properties
- Image support
- Local browser version history
- Zoom, grid, and snap controls
- Undo and redo
- Multi-select
- Align, distribute, and layer tools
- Lock and unlock
- Report bands: Page Header, Detail, and Page Footer
- Data Fields panel
- Field search and binding picker
- Sample data editor
- Placeholder/sample data canvas toggle
- `template.data.sample` support
- `template.data.fields` support
- Repeating Detail rows
- Row-relative bindings for repeating data
- Flask-hosted preview and PDF export
- CLI commands for validation, inspection, and rendering

Not implemented yet:

- Full table component
- Barcode/QR rendering
- Full pagination and multi-page repeat overflow
- Group headers and footers
- Django adapter
- FastAPI adapter
- Production packaging and public release

## Screenshots

Screenshots coming soon. Place screenshots in `docs/assets/` and reference them here.

## Architecture Rules

`slim_report_core` must never import Flask, Django, FastAPI, SQLAlchemy, or any web framework.

Rendering belongs in `slim_report_core`. Framework adapters such as `slim_report_flask` handle framework concerns: routes, requests, responses, provider registration, storage orchestration, and calling the core.

Serialization belongs at the persistence boundary. JSON templates are converted into `Report` objects through `slim_report_core.serialization`; renderers receive `Report`, not JSON.

The designer UI is framework-agnostic static HTML/CSS/JavaScript. Framework adapters host the same files and provide load, save, preview, and export APIs.

## Packages

- `slim_report_core`: report models, expression resolution, rendering, widgets, exporters, and pure Python API
- `slim_report_designer_ui`: framework-agnostic static designer UI
- `slim_report_flask`: Flask extension, blueprint routes, template storage, and provider registration
- `slim_report_cli`: command-line interface using only `slim_report_core`
- `slim_report_django`: future Django adapter placeholder
- `slim_report_fastapi`: future FastAPI adapter placeholder

## Installation

Install local packages in editable mode from the repository root:

```bash
python -m pip install -e packages/slim_report_core
python -m pip install -e packages/slim_report_designer_ui
python -m pip install -e packages/slim_report_flask
python -m pip install -e packages/slim_report_cli
```

`slim_report_core` depends on ReportLab for PDF export. `slim_report_flask` depends on Flask and the designer UI package.

For development tools:

```bash
python -m pip install pytest ruff
python -m pytest
python -m ruff check packages tests
```

## Quick Start

### A. Pure Python Report

```python
from pathlib import Path

from slim_report_core import Report

report = Report("CBC Report")
page = report.page()

data = {"patient": {"name": "Juan Dela Cruz"}, "result": {"hgb": "14.2"}}

page.text("Complete Blood Count", x=50, y=40, width=300, height=28, font_size=18, bold=True)
page.field("patient.name", x=50, y=90, width=250, height=20)
page.line(x=50, y=120, width=500)
page.rectangle(x=50, y=150, width=500, height=80)
page.field("result.hgb", x=70, y=175, width=120, height=20)

html = report.render_html(data)
pdf_bytes = report.render_pdf(data)

Path("cbc.html").write_text(html, encoding="utf-8")
Path("cbc.pdf").write_bytes(pdf_bytes)
```

Missing fields render as an empty string.

### B. Static Designer UI

```bash
python examples/designer_static_server/serve.py
```

Open:

```text
http://127.0.0.1:8008/
```

The static designer works without Flask. JSON import/export works, local browser version history works, and `data.sample` / `data.fields` can be edited. PDF export requires a backend API.

### C. Flask Designer UI

```bash
python examples/flask_app/app.py
```

Open:

```text
http://127.0.0.1:5000/report-designer/designer?template=lab_result
http://127.0.0.1:5000/report-designer/designer?template=cerebro_cbc
http://127.0.0.1:5000/report-designer/designer?template=repeating_lab_result
```

The Flask example loads templates from `examples/flask_app/sample_templates/`. Preview works, PDF export works, and sample/provider data can be used for field rendering. The `repeating_lab_result` template demonstrates repeating Detail rows over array data.

## Serialization

Use `JSONSerializer` when you want to load or save JSON:

```python
from slim_report_core.serialization import JSONSerializer

serializer = JSONSerializer()
serializer.save(report, "template.json")
loaded = serializer.load("template.json")
```

JSON is optional after a `Report` exists. Applications can create reports directly in Python or load them through another serializer/storage boundary later.

## Existing JSON Templates

```python
from slim_report_core import render_html, render_pdf
from slim_report_core.serialization import JSONSerializer

report = JSONSerializer().load("template.json")
data = {"patient": {"name": "Juan Dela Cruz"}}

html = render_html(report, data)
pdf_bytes = render_pdf(report, data)
```

## CLI

```bash
slim-report validate examples/flask_app/sample_templates/lab_result.json
slim-report inspect examples/flask_app/sample_templates/lab_result.json
slim-report render examples/flask_app/sample_templates/lab_result.json data.json output.html --format html
slim-report render examples/flask_app/sample_templates/lab_result.json data.json output.pdf
```

The CLI accepts JSON files as input, but commands deserialize to `Report` before validation, inspection, or rendering.

## Documentation

- [Documentation index](docs/README.md)
- [Designer UI](docs/designer-ui.md)
- [Flask integration](docs/flask-integration.md)
- [JSON template schema](docs/json-template-schema.md)
- [Data Fields](docs/data-fields.md)
- [Repeating Detail rows](docs/repeating-detail-rows.md)
- [Public API](docs/public-api.md)
- [Architecture](docs/architecture.md)
- [Roadmap](docs/roadmap.md)

## Repository Layout

```text
packages/
  slim_report_core/
  slim_report_designer_ui/
  slim_report_flask/
  slim_report_django/
  slim_report_fastapi/
  slim_report_cli/
examples/
  designer_static_server/
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
