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

Use Prompt 1 first, bro. Then run/test, commit, then continue Prompt 2.