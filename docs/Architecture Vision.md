Architecture Vision
slim-report-designer/
│
├── packages/
│   ├── slim_report_core/
│   ├── slim_report_flask/
│   ├── slim_report_django/
│   ├── slim_report_fastapi/
│   └── slim_report_cli/
│
├── examples/
│   ├── pure_python/
│   ├── flask_app/
│   ├── django_app/
│   ├── fastapi_app/
│   └── lis_demo/
│
├── docs/
├── tests/
├── README.md
├── LICENSE
└── pyproject.toml

Core rule:

The core engine must never import Flask, Django, FastAPI, or any web framework.
Master Phases
Phase 0  - Vision and monorepo foundation
Phase 1  - Core report model
Phase 2  - JSON schema and validation
Phase 3  - Expression resolver
Phase 4  - Data context system
Phase 5  - Widget registry
Phase 6  - Core widgets
Phase 7  - Exporter registry
Phase 8  - HTML exporter
Phase 9  - PDF exporter
Phase 10 - Pure Python API
Phase 11 - CLI renderer
Phase 12 - Flask adapter
Phase 13 - Flask visual designer shell
Phase 14 - Template storage abstraction
Phase 15 - Database storage for Flask
Phase 16 - Django adapter
Phase 17 - FastAPI adapter
Phase 18 - Advanced widgets
Phase 19 - Bands, tables, pagination
Phase 20 - Permissions, versioning, assets
Phase 21 - Examples and demos
Phase 22 - Tests and docs
Phase 23 - Public release
Phase 0 — Vision and Foundation
Create a professional Python monorepo for an open-source project named slim-report-designer.

This project is a framework-agnostic reporting platform for Python applications, with first-class support for Flask and future support for Django, FastAPI, CLI, and pure Python apps.

Create this structure:

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

docs/
tests/
scripts/

Add:
- README.md
- LICENSE
- CHANGELOG.md
- CONTRIBUTING.md
- CODE_OF_CONDUCT.md
- pyproject.toml

The README should clearly state:

“Slim Report Designer is an open-source, framework-agnostic reporting platform for Python applications. It provides a JSON-based report engine, pluggable widgets, multiple exporters, and framework adapters starting with Flask.”

Do not implement features yet. Focus on clean structure, packaging, and future extensibility.
Phase 1 — Core Report Model
Implement the framework-agnostic report model in packages/slim_report_core.

Create classes:

- Report
- ReportTemplate
- ReportPage
- ReportObject
- ReportBand
- ReportAsset
- ReportMetadata

The core package must not import Flask, Django, FastAPI, SQLAlchemy, or any web framework.

The Report class should support:

- load_from_dict()
- load_from_json()
- to_dict()
- to_json()
- add_object()
- remove_object()
- get_object()

Use dataclasses where appropriate.

Add a simple example in examples/pure_python showing how to create a report with text objects and export the JSON.
Phase 2 — JSON Schema and Validation
Create the official JSON schema system for slim_report_core.

Create:

packages/slim_report_core/schema.py

Support report template fields:

- version
- metadata
- page
- variables
- parameters
- data_sources
- bands
- objects
- assets

Each object should support:

- id
- type
- name
- x
- y
- width
- height
- rotation
- opacity
- visible
- locked
- style
- bindings

Create helpers:

- validate_template(template)
- validate_object(obj)
- normalize_template(template)
- create_default_template()

The validator should return:

(is_valid, errors)

Make validation friendly and extensible, not overly strict.
Phase 3 — Expression Resolver
Implement expression resolving in slim_report_core.

Create:

packages/slim_report_core/expressions.py

Support expressions:

{{ patient.name }}
{{ order.id }}
{{ result.HGB }}
{{ today() }}
{{ now() }}
{{ page }}
{{ pages }}

Support nested dictionaries and object attributes.

Add:

- resolve_expression(expression, data, context=None)
- resolve_text(text, data, context=None)

Example:

"Patient: {{ patient.name }}"

should become:

"Patient: Juan Dela Cruz"

Missing values should return empty string or a configurable fallback.

Do not use eval.

Keep it safe.
Phase 4 — Data Context System
Implement a framework-agnostic data context system.

Create:

packages/slim_report_core/data.py

Classes:

- DataContext
- DataProviderRegistry

DataProviderRegistry should support:

- register(name, func)
- get(name)
- list()
- resolve(name, *args, **kwargs)

DataContext should hold:

- data
- parameters
- variables
- runtime context like page/page count

No Flask or database dependencies.
Phase 5 — Widget Registry
Implement the widget plugin system in slim_report_core.

Create:

packages/slim_report_core/widgets/

Files:

- base.py
- registry.py
- text.py
- field.py
- line.py
- rectangle.py
- image.py
- table.py
- barcode.py
- qrcode.py
- chart.py

BaseWidget should define:

- type
- label
- icon
- default_config()
- validate(obj)
- render_html(obj, data, context)
- render_pdf(canvas, obj, data, context)

WidgetRegistry should support:

- register(widget)
- get(type_name)
- list()
- has(type_name)

Fully implement text, field, line, and rectangle first.
Use placeholders for advanced widgets.
Phase 6 — Core Widgets
Fully implement the first production-ready widgets:

- text
- field
- line
- rectangle

Text widget:
- static text
- font size
- bold
- italic
- color
- alignment

Field widget:
- binding path
- format
- fallback value

Line widget:
- stroke width
- stroke color

Rectangle widget:
- border width
- border color
- fill color
- border radius

Each widget must render to HTML and PDF through the exporter interface.
Phase 7 — Exporter Registry
Implement exporter plugin architecture.

Create:

packages/slim_report_core/exporters/

Files:

- base.py
- registry.py
- html.py
- pdf.py
- image.py

BaseExporter should define:

- name
- export(report_template, data, options=None)

ExporterRegistry should support:

- register(exporter)
- get(name)
- list()
- has(name)

Register built-in exporters:

- html
- pdf

Image exporter can be placeholder for now.
Phase 8 — HTML Exporter
Implement the HTML exporter in slim_report_core.

The HTML exporter should render report JSON into standalone HTML.

Support:

- page size
- margins
- absolute positioning
- text
- field
- line
- rectangle

Output should visually match the report designer canvas.

Make it usable for browser preview and print preview.

Add pure Python example:

render_html.py

It should load sample JSON and sample data, then generate output.html.
Phase 9 — PDF Exporter
Implement the PDF exporter using ReportLab.

Support:

- A4
- Letter
- portrait
- landscape
- margins
- text
- field
- line
- rectangle

The PDF exporter should live in slim_report_core, not in Flask.

Add pure Python example:

render_pdf.py

It should load sample JSON and sample data, then generate output.pdf.
Phase 10 — Pure Python API
Create a clean developer API for pure Python usage.

Target usage:

from slim_report_core import Report

report = Report.load_json("template.json")
pdf_bytes = report.render(data, exporter="pdf")

report.save_pdf("output.pdf", data)
html = report.render(data, exporter="html")

Implement these convenience methods.

Add documentation in docs/pure-python.md.
Phase 11 — CLI Renderer
Create the CLI package slim_report_cli.

Command examples:

slim-report render template.json data.json output.pdf
slim-report render template.json data.json output.html --format html
slim-report validate template.json
slim-report inspect template.json

Use argparse or typer.

The CLI should use slim_report_core only.

It must not depend on Flask, Django, or FastAPI.
Phase 12 — Flask Adapter
Create the Flask adapter package slim_report_flask.

Implement:

- SlimReportDesigner extension class
- Flask blueprint
- configurable URL prefix
- provider registration
- template routes
- preview route
- export PDF route

Usage:

from slim_report_flask import SlimReportDesigner

designer = SlimReportDesigner()
designer.init_app(app)

@designer.provider("lab_result")
def lab_result(record_id):
    return {...}

The Flask adapter should use slim_report_core for rendering.
Do not duplicate rendering logic in Flask.
Phase 13 — Flask Visual Designer Shell
Build the first Flask visual designer shell.

Create pages:

/report-designer/templates
/report-designer/templates/new
/report-designer/templates/<id>/designer
/report-designer/templates/<id>/preview
/report-designer/templates/<id>/export/pdf/<record_id>

Designer UI should have:

- top toolbar
- left toolbox
- center A4 canvas
- right property inspector
- bottom status bar

Use Bootstrap 5 and vanilla JavaScript first.

Support adding:

- text
- field
- line
- rectangle

Save template JSON through Flask route.
Phase 14 — Template Storage Abstraction
Create a framework-agnostic template storage abstraction.

In slim_report_core create:

storage/
  base.py
  file_storage.py
  memory_storage.py

BaseTemplateStorage should support:

- list_templates()
- get_template(id_or_code)
- save_template(template)
- delete_template(id_or_code)

Implement:

- MemoryTemplateStorage
- FileTemplateStorage

Flask adapter should be able to use this abstraction.
Phase 15 — Database Storage for Flask
Implement database-backed template storage for Flask.

In slim_report_flask create SQLAlchemy models:

- ReportTemplate
- ReportVersion
- ReportAsset
- ReportPermission

Do not put SQLAlchemy dependency in slim_report_core.

The Flask adapter should support:

SLIM_REPORT_STORAGE = "database"
SLIM_REPORT_STORAGE = "file"

Database mode should store templates in SQLAlchemy.
File mode should store templates as JSON files.
Phase 16 — Django Adapter
Create initial Django adapter package slim_report_django.

Goal: skeleton only.

Add:

- Django app config
- urls.py
- views.py
- models.py
- template list view
- preview view
- PDF export view

The Django adapter should use slim_report_core for rendering.

Do not fully implement visual designer yet.
Focus on proving the adapter architecture works.
Phase 17 — FastAPI Adapter
Create initial FastAPI adapter package slim_report_fastapi.

Add:

- APIRouter factory
- template list endpoint
- preview HTML endpoint
- PDF export endpoint

The FastAPI adapter should use slim_report_core.

Do not implement database storage yet.
Use file or memory storage first.
Phase 18 — Advanced Widgets
Implement advanced widgets in slim_report_core:

- image
- barcode
- qrcode
- signature
- chart placeholder

Image:
- file path
- base64
- fit modes: contain, cover, stretch

QR code:
- use qrcode package
- bind value from data

Barcode:
- Code128 first
- bind value from data

Signature:
- image-based signature
- placeholder signature line

Support HTML and PDF rendering.
Phase 19 — Bands, Tables, Pagination
Implement real reporting features.

Support bands:

- title
- page_header
- detail
- page_footer
- summary

Support repeating detail bands from list data.

Example:

"data_path": "results"

Implement table widget:

{
  "type": "table",
  "data_path": "results",
  "columns": [
    {"header": "Test", "field": "name"},
    {"header": "Result", "field": "value"},
    {"header": "Unit", "field": "unit"}
  ]
}

Add basic pagination:

- detect overflow
- continue rows on next page
- repeat page header
- render page footer
- support page number expressions
Phase 20 — Permissions, Versions, Assets
Implement optional platform features.

Core should define interfaces only:

- PermissionChecker
- VersionManager
- AssetStorage

Framework adapters should implement actual integrations.

Flask adapter should support:

- permission hooks
- template version history
- asset upload
- asset listing
- restore template version

Do not force authentication library dependency.
Allow host app to provide hooks.
Phase 21 — Examples and Demos
Create full examples:

1. pure_python
- create report from JSON
- render HTML
- render PDF

2. flask_app
- Flask extension usage
- visual designer
- template storage
- PDF export

3. lis_demo
- patient
- order
- CBC results
- laboratory result report

4. pos_demo
- customer
- invoice
- VAT
- receipt printing

5. fastapi_app
- basic preview/export API

6. django_app
- basic preview/export views
Phase 22 — Tests and Documentation
Add tests and documentation.

Tests:

- report model
- JSON validation
- expression resolver
- data provider registry
- widget registry
- HTML exporter
- PDF exporter
- CLI commands
- Flask adapter initialization
- Flask routes

Docs:

- introduction
- architecture
- pure Python usage
- Flask integration
- Django integration
- FastAPI integration
- CLI usage
- JSON schema
- widgets
- exporters
- storage
- roadmap
Phase 23 — Public Release
Prepare the project for public release.

Add:

- GitHub Actions
- issue templates
- pull request template
- release checklist
- package metadata
- build script
- test script
- docs build placeholder

Ensure:

pip install -e .

works.

Ensure:

python -m build

works.

Prepare initial release:

v0.1.0 Developer Preview

Release description:

“Slim Report Designer v0.1.0 introduces the framework-agnostic Python reporting core, JSON templates, pure Python rendering, CLI support, and the first Flask adapter.”
New Version Roadmap
v0.1.0 - Core engine, JSON model, HTML/PDF export, pure Python API
v0.2.0 - CLI renderer
v0.3.0 - Flask adapter
v0.4.0 - Flask visual designer alpha
v0.5.0 - Widget plugin system stable
v0.6.0 - Tables, bands, pagination
v0.7.0 - Barcode, QR, images, signatures
v0.8.0 - Django and FastAPI adapters
v0.9.0 - Permissions, versioning, assets
v1.0.0 - Stable public release
The most important architecture principle
slim_report_core must remain pure Python.

No Flask.
No Django.
No FastAPI.
No SQLAlchemy.
No web assumptions.

Everything else is adapter/plugin layer.

That is how this becomes bigger than Flask, bro.