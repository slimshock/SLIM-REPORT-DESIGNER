VS Code Codex one-by-one.

VS Code Codex Prompt 1 — Create Project Foundation

Create a professional Python monorepo named slim-report-designer.

This project is an open-source, framework-agnostic reporting platform for Python applications, with first-class support for Flask and future support for Django, FastAPI, CLI, and pure Python apps.

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
pos_demo/

docs/
tests/
scripts/

Add these root files:

README.md
LICENSE
CHANGELOG.md
CONTRIBUTING.md
CODE_OF_CONDUCT.md
pyproject.toml
.gitignore

Important architecture rule:

The slim_report_core package must never import Flask, Django, FastAPI, SQLAlchemy, or any web framework.

The README should describe the vision:

“Slim Report Designer is an open-source, framework-agnostic reporting platform for Python applications. It provides a JSON-based report engine, pluggable widgets, multiple exporters, and framework adapters starting with Flask.”

Do not implement full features yet. Focus on clean structure, packaging, and future extensibility.


------------------------------------------------------


VS Code Codex Prompt 2 — Implement Core Report Model

Implement the framework-agnostic core package in:

packages/slim_report_core/

Create the following modules:

init.py
report.py
models.py
schema.py
exceptions.py
constants.py
utils.py

Create dataclass-based models:

Report
ReportTemplate
ReportPage
ReportObject
ReportBand
ReportAsset
ReportMetadata

The Report class should support:

load_from_dict()
load_from_json()
to_dict()
to_json()
add_object()
remove_object()
get_object()

Add create_default_template() that returns a valid empty report template with:

version
metadata
page
objects
bands
assets

Do not import Flask, Django, FastAPI, SQLAlchemy, or any web framework.

Add an example in:

examples/pure_python/create_report.py

The example should create a report with a text object and save it as JSON.


------------------------------------------------------


VS Code Codex Prompt 3 — Expression Resolver and Data Context

Implement expression resolving in slim_report_core.

Create:

packages/slim_report_core/expressions.py
packages/slim_report_core/data.py

Support expressions like:

{{ patient.name }}
{{ order.id }}
{{ result.HGB }}
{{ today() }}
{{ now() }}
{{ page }}
{{ pages }}

Functions:

resolve_expression(expression, data, context=None)
resolve_text(text, data, context=None)

Rules:

Support nested dictionaries.
Support object attributes.
Do not use eval.
Missing values should return empty string.
Function support should be safe and limited.

Create DataContext and DataProviderRegistry.

DataProviderRegistry should support:

register(name, func)
get(name)
list()
resolve(name, *args, **kwargs)

Add tests for expression resolving.


------------------------------------------------------


VS Code Codex Prompt 4 — Widget and Exporter System

Implement the plugin systems for widgets and exporters.

Create:

packages/slim_report_core/widgets/
packages/slim_report_core/exporters/

Widget system:

BaseWidget
WidgetRegistry

Widgets:

text
field
line
rectangle

Each widget should support:

type
label
default_config()
validate(obj)
render_html(obj, data, context)
render_pdf(canvas, obj, data, context)

Exporter system:

BaseExporter
ExporterRegistry

Exporters:

HTMLExporter
PDFExporter

The HTML exporter should render absolute-positioned HTML.

The PDF exporter should use ReportLab.

Support A4, Letter, portrait, landscape, text, field, line, and rectangle.

Do not import Flask or any web framework.



------------------------------------------------------



VS Code Codex Prompt 5 — Pure Python API and CLI

Create a clean pure Python API.

Target usage:

from slim_report_core import Report

report = Report.load_json("template.json")
html = report.render(data, exporter="html")
pdf_bytes = report.render(data, exporter="pdf")
report.save_pdf("output.pdf", data)

Then create CLI package:

packages/slim_report_cli/

Command examples:

slim-report render template.json data.json output.pdf
slim-report render template.json data.json output.html --format html
slim-report validate template.json
slim-report inspect template.json

The CLI must use only slim_report_core.

Do not depend on Flask, Django, or FastAPI.



------------------------------------------------------



VS Code Codex Prompt 6 — Flask Adapter

Create the Flask adapter package:

packages/slim_report_flask/

Implement:

SlimReportDesigner extension class
Flask blueprint
config defaults
provider registration
template routes
preview route
PDF export route

Usage:

from slim_report_flask import SlimReportDesigner

designer = SlimReportDesigner()
designer.init_app(app)

@designer.provider("lab_result")
def lab_result(record_id):
return {...}

Routes:

/report-designer/health
/report-designer/templates
/report-designer/templates/new
/report-designer/templates/<id>/designer
/report-designer/templates/<id>/preview/<record_id>
/report-designer/templates/<id>/export/pdf/<record_id>

The Flask adapter must use slim_report_core for rendering.

Do not duplicate rendering logic inside Flask.



------------------------------------------------------



# Prompt 7 — Report Preview and PDF Generation

We already completed the first 6 foundation prompts for Slim Report Designer.

Now implement the first working report generation flow.

Goal:
A user should be able to load a report template JSON, provide data, preview it as HTML, and export it as PDF.

Important architecture rule:
- slim_report_core must do all rendering logic.
- slim_report_flask must only handle routes, request/response, storage, and calling the core.
- Do not duplicate rendering logic in Flask.

Implement the following:

1. In slim_report_core

Create or improve:

packages/slim_report_core/rendering/
  __init__.py
  context.py
  html_renderer.py
  pdf_renderer.py

The render flow should support:

- Report template dict
- Data dict
- Export format: html or pdf
- Page size A4 and Letter
- Portrait and landscape
- Absolute positioned report objects

Supported objects for now:

- text
- field
- line
- rectangle

Text object example:

{
  "id": "title1",
  "type": "text",
  "x": 50,
  "y": 40,
  "width": 400,
  "height": 30,
  "text": "Laboratory Result",
  "style": {
    "font_size": 18,
    "bold": true
  }
}

Field object example:

{
  "id": "patient_name",
  "type": "field",
  "x": 50,
  "y": 90,
  "width": 300,
  "height": 20,
  "binding": "patient.name",
  "style": {
    "font_size": 12
  }
}

Line object example:

{
  "id": "line1",
  "type": "line",
  "x": 50,
  "y": 130,
  "width": 500,
  "height": 0,
  "style": {
    "stroke_width": 1
  }
}

Rectangle object example:

{
  "id": "box1",
  "type": "rectangle",
  "x": 50,
  "y": 150,
  "width": 500,
  "height": 100,
  "style": {
    "border_width": 1
  }
}

2. HTML Preview

Implement HTML rendering that outputs a full HTML document.

The output should include:

- page wrapper
- white page background
- A4/Letter dimensions in pixels
- absolute-positioned objects
- basic CSS
- field values resolved from data

Field resolution:
"patient.name" should resolve from:

{
  "patient": {
    "name": "Juan Dela Cruz"
  }
}

If a field is missing, show empty string.

3. PDF Export

Implement PDF rendering using ReportLab.

The PDF should:

- render text
- render fields
- render lines
- render rectangles
- respect x/y positioning
- use top-left coordinate style in template JSON
- convert internally to ReportLab bottom-left coordinates

Return PDF as bytes.

4. Public API

Add methods to the core API:

from slim_report_core import render_html, render_pdf

html = render_html(template_json, data)
pdf_bytes = render_pdf(template_json, data)

Also support:

from slim_report_core import Report

report = Report.load_from_dict(template_json)
html = report.render_html(data)
pdf_bytes = report.render_pdf(data)

5. Flask Adapter

In slim_report_flask, implement routes:

GET /report-designer/templates/<id>/preview/<record_id>
GET /report-designer/templates/<id>/export/pdf/<record_id>

Preview route:
- load template
- call provider using record_id
- call slim_report_core.render_html()
- return HTML response

PDF route:
- load template
- call provider using record_id
- call slim_report_core.render_pdf()
- return PDF using Flask send_file or Response

6. Demo Provider

In examples/flask_app/app.py, add provider:

@designer.provider("lab_result")
def lab_result(record_id):
    return {
        "patient": {
            "name": "JUAN DELA CRUZ",
            "age": "35",
            "sex": "MALE"
        },
        "order": {
            "id": record_id,
            "date": "2026-07-05"
        },
        "result": {
            "HGB": "14.5",
            "WBC": "7.2",
            "PLT": "250"
        }
    }

7. Demo Template

Add sample template JSON:

examples/flask_app/sample_templates/lab_result.json

It should render:

- title: LABORATORY RESULT
- patient name
- age / sex
- order id
- HGB
- WBC
- PLT
- one line separator
- one rectangle around results

8. Tests

Add tests for:

- field value resolving
- HTML rendering contains expected patient name
- PDF rendering returns bytes starting with %PDF
- missing field does not crash

9. Keep code clean

Use small functions.
Avoid framework imports in slim_report_core.
Add docstrings where useful.


------------------------------------------------------



# Prompt 8 — Designer Save, Preview Button, and PDF Button

Improve the Flask visual designer so the user can save, preview, and export reports.

Requirements:

1. Designer page should have buttons:
- Save
- Preview
- Export PDF

2. Save button:
POST template JSON to:
/report-designer/templates/<id>/designer/save

3. Preview button:
Open:
/report-designer/templates/<id>/preview/sample

4. Export PDF button:
Open:
/report-designer/templates/<id>/export/pdf/sample

5. The designer should start with sample objects if template is empty:
- title text
- patient field
- result fields

6. Make sure the saved JSON works with the core HTML and PDF renderer.

7. Keep JavaScript modular and simple.


------------------------------------------------------






------------------------------------------------------






------------------------------------------------------


