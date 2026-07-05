# Slim Report Designer

Slim Report Designer is an open-source, framework-agnostic reporting platform for Python applications. It provides a Report-first Python API, JSON serialization, pluggable widgets, multiple exporters, and framework adapters starting with Flask.

## Current Status

The project is in early alpha. The current working flow supports creating reports with Python, loading and saving JSON templates, resolving data fields, previewing as HTML, and exporting as PDF.

Implemented now:

- Framework-agnostic `slim_report_core`
- `Report` domain model with pages, metadata, objects, styles, assets, bands, and layers
- Serialization layer with `JSONSerializer` for JSON to `Report` conversion
- Domain validation with structured `Report.validate()` results
- Deep cloning for reports, pages, objects, styles, and assets
- Object query helpers such as `find()`, `fields()`, and `text_objects()`
- Framework-independent report events for render/export and object/page changes
- Report-first public API for everyday report creation
- ObjectFactory for consistent object construction across API helpers, serializers, designers, and AI integrations
- Fluent Builder API for constructing `Report` domain objects
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

Serialization belongs at the persistence boundary. JSON templates are converted into `Report` objects through `slim_report_core.serialization`; low-level renderers receive `Report`, not JSON.

JSON is the first built-in persistence format, not a requirement for using the core. YAML, XML plugins, database storage, and REST-backed storage should all convert to and from `Report`.

Validation belongs to the `Report` domain model. Use `report.validate()` after loading or building a report; normal validation failures return structured errors instead of raising exceptions.

Cloning belongs to the domain model too. `report.clone()` creates a deep clone with new ids by default; use `report.clone(new_ids=False)` only when duplicate ids are intentional.

Querying also belongs to `Report`: use `report.find("object_id")`, `report.find(lambda obj: ...)`, `report.fields()`, and `report.text_objects()` for developer-friendly object access.

Events are exposed through `report.on()` and `report.off()` for framework-independent extension points such as audit logging, metrics, or designer synchronization.

Builder code creates `Report` domain objects directly. It does not know about JSON, Flask, or rendering.

For everyday development, `Report` is the primary API. Builders are optional convenience helpers.

## Packages

- `slim_report_core`: report models, expression resolution, rendering, widgets, exporters, and pure Python API
- `slim_report_flask`: Flask extension, blueprint routes, template storage, and provider registration
- `slim_report_cli`: command-line interface using only `slim_report_core`
- `slim_report_django`: future Django adapter placeholder
- `slim_report_fastapi`: future FastAPI adapter placeholder

## Beginner Report API

```python
from slim_report_core import Report

report = Report("CBC Report")
page = report.page()

data = {"patient": {"name": "JUAN DELA CRUZ"}}

page.text("Complete Blood Count", x=50, y=40, font_size=18, bold=True)
page.field("patient.name", x=50, y=90)
page.line(x=50, y=120, width=500)
page.rectangle(x=40, y=150, width=520, height=120)

result = report.validate()
html = report.render_html(data)
pdf_bytes = report.render_pdf(data)
```

Missing fields render as an empty string.

## Serialization

Use `JSONSerializer` only when you want to load or save JSON:

```python
from slim_report_core.serialization import JSONSerializer

serializer = JSONSerializer()
serializer.save(report, "template.json")
loaded = serializer.load("template.json")
```

JSON is optional once a `Report` exists. Future serializers can support YAML, XML plugins, database records, REST payloads, or binary packages without changing renderers.

## Existing JSON Templates

```python
from slim_report_core import render_html, render_pdf
from slim_report_core.serialization import JSONSerializer

report = JSONSerializer().load("template.json")
data = {"patient": {"name": "JUAN DELA CRUZ"}}

html = render_html(report, data)
pdf_bytes = render_pdf(report, data)
```

Optional builder conveniences reduce boilerplate for common report structure:

```python
from slim_report_core import ReportBuilder

report = (
    ReportBuilder()
    .metadata(title="Invoice", subtitle="July Billing")
    .landscape()
    .margin(36)
    .header("ACME Billing")
    .title("Invoice")
    .subtitle("July Billing")
    .field("customer.name", x=50, y=130)
    .footer("Page {{ page }}")
    .build()
)
```

Reusable styles can be shared across page calls and can inherit from base styles:

```python
from slim_report_core import Report, Style

base_style = Style(font_family="Helvetica", font_size=12)
title_style = base_style.inherit(font_size=18, bold=True)

report = Report("Laboratory Report")
page = report.page()
page.text("Laboratory Report", x=50, y=40, style=title_style)
page.text("Final Result", x=50, y=80, style=title_style)
```

Use `Position` and `Size` when explicit geometry reads better than raw coordinates:

```python
from slim_report_core import Position, Report, Size

report = Report("Laboratory Report")
page = report.page()
page.text("Laboratory Report", position=Position(50, 40), size=Size(300, 30))
page.field("patient.name", position=Position(50, 90), size=Size(300, 20))
page.rectangle(position=Position(50, 150), size=Size(500, 100))
```

Multi-page reports can be built with explicit pages:

```python
report = Report("Invoice")
cover = report.page()
cover.text("Invoice", x=50, y=40)
cover.field("customer.name", x=50, y=80)

terms = report.new_page("Letter")
terms.text("Terms", x=50, y=40)
```

Use `JSONSerializer` only when you want to persist the built report.

## AI-Friendly Generation

AI tools should generate the same public API that humans use:

```python
from slim_report_core import Report, Style

title_style = Style(font_size=18, bold=True)

report = Report("Laboratory Result")
page = report.page()
page.text("LABORATORY RESULT", x=50, y=40, style=title_style)
page.field("patient.name", x=50, y=90)
page.field("result.HGB", x=50, y=140)
```

When AI needs a storage format, it can generate JSON for `JSONSerializer`, but downstream code should still validate and render the resulting `Report`.

## Validation

```python
from slim_report_core.serialization import JSONSerializer

report = JSONSerializer().load("template.json")
result = report.validate()

if not result.is_valid:
    for error in result.errors:
        print(error.path, error.code, error.message)
```

The CLI uses the same validation API:

```bash
slim-report validate examples/flask_app/sample_templates/lab_result.json
```

For explicit persistence control:

```python
from slim_report_core import render_html
from slim_report_core.serialization import JSONSerializer

serializer = JSONSerializer()
report = serializer.load("template.json")
html = render_html(report, data)
serializer.save(report, "template.json")
```

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
