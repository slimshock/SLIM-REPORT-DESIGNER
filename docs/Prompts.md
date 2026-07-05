# Prompt Archive

This file is historical prompt material. It records earlier planning requests and may contain old
JSON-first examples such as `Report.load_json()` or `to_json()`. Current architecture is
Report-first: use `docs/architecture.md`, `docs/public-api.md`, and ADR-0007 as the source of truth.

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


# Prompt 9 — Architecture Review Sprint

Review the current Slim Report Designer codebase after implementing foundation, Flask adapter, HTML preview, and PDF export.

Goal:
Improve architecture, naming, boundaries, tests, and documentation without adding major new features.

Check and improve:

1. Package boundaries
- slim_report_core must not import Flask, Django, FastAPI, SQLAlchemy, or web framework code.
- slim_report_flask should only handle Flask routes, requests, responses, provider registration, and storage orchestration.
- Rendering must remain in slim_report_core.

2. Public API
Review whether these APIs are clean and Pythonic:

from slim_report_core import render_html, render_pdf
from slim_report_core import Report

report = Report.load_from_dict(template_json)
html = report.render_html(data)
pdf = report.render_pdf(data)

Improve naming only if clearly better.

3. Renderer structure
Make sure HTML and PDF rendering share common helpers where appropriate:
- page size handling
- orientation
- coordinate conversion
- field resolution
- style normalization

Avoid duplicated logic.

4. Tests
Add or improve tests for:
- core does not import Flask
- HTML rendering
- PDF rendering
- missing fields
- field expression resolution
- Flask preview route
- Flask PDF export route

5. Documentation
Update README and docs with:
- current status
- how to run Flask example
- how to preview report
- how to export PDF
- pure Python rendering example

6. Developer quality
Add type hints where useful.
Add docstrings for public functions/classes.
Remove debug code.
Remove unused files/imports.
Ensure formatting is clean.

Do not add tables, barcode, QR, images, designer drag/drop, or pagination in this sprint.
This sprint is for stabilization only.



------------------------------------------------------






------------------------------------------------------




Prompt 1 - The Report Domain Model

------------------------------------------------------

Sprint 3
"The Report"

Mission

Transform Report into the heart of Slim Report Designer.

Background

At this point HTML preview and PDF rendering are working.

However the Report model is still strongly coupled to JSON serialization.

The objective of this sprint is to make Report the true domain model.

JSON should become only one persistence format.

Architecture Constraints

The core package must remain framework agnostic.

No Flask.

No Django.

No SQLAlchemy.

No web assumptions.

Objectives

Create a clean Report object model.

Review every existing model.

Report

Page

Band

Layer (if appropriate)

Object

Style

Binding

Margin

Metadata

Asset

Report should expose a clean API.

Example:

report.pages

report.metadata

report.objects

report.styles

report.assets

Create helper methods:

add_page()

remove_page()

find_object()

add_asset()

clone()

copy()

Do NOT focus on rendering.

Focus only on the domain model.

Acceptance Criteria

Report becomes the single source of truth.

Renderer consumes Report.

JSON serializer converts JSON ⇄ Report.

Builder API can later target Report directly.

Documentation

Update architecture docs describing the new domain model.
Prompt 2
Serializer Layer
Sprint 3

Create a serialization layer.

Current implementation loads JSON directly.

Replace this with serializers.

Create package:

serialization/

Implement:

BaseSerializer

JSONSerializer

Responsibilities

JSONSerializer

JSON -> Report

Report -> JSON

Future serializers:

YAML

Database

REST

Binary

The renderer should never know JSON exists.

The renderer receives Report only.

Add tests.

Document serializer architecture.
Prompt 3
Rendering Refactor
Sprint 3

Refactor renderers.

Current renderer may still receive dictionaries.

Update architecture so:

Report
        ↓
Renderer
        ↓
HTML

Report
        ↓
Renderer
        ↓
PDF

Renderers must never depend on JSON.

Use the Report object exclusively.

Update all tests.
Prompt 4
Report Validation
Sprint 3

Move validation from JSON into Report.

Implement:

Report.validate()

Validation should check:

page exists

page size valid

objects valid

unique ids

bindings

styles

assets

Return structured validation errors.

Validation should not throw exceptions for normal validation failures.

Document validation API.
Prompt 5
Report Copy / Clone
Sprint 3

Implement deep cloning.

Support:

report.clone()

page.clone()

object.clone()

style.clone()

Assets should optionally support shared references.

Clone should preserve IDs only when requested.

Support:

clone(new_ids=True)

Document behavior.
Prompt 6
Report Query API
Sprint 3

Create developer-friendly query methods.

Examples

report.find(id)

report.find_by_name()

report.objects()

report.text_objects()

report.fields()

report.images()

report.tables()

Support predicates.

Example

report.find(lambda o: o.type=="text")

Document examples.
Prompt 7
Report Events
Sprint 3

Introduce event system.

Events:

before_render

after_render

before_export

after_export

object_added

object_removed

page_added

page_removed

Events should be framework independent.

Use observer pattern.

Document extension points.
Prompt 8
Architecture Cleanup
Sprint 3

Review entire architecture.

Questions

Does Report know JSON?

If yes remove it.

Does Renderer know JSON?

If yes remove it.

Can Builder API target Report?

Can Designer target Report?

Can Flask target Report?

Can CLI target Report?

Can AI target Report?

Update architecture diagrams.

Update ADRs if needed.






-----------------------------------


Sprint 4: The Builder
Mission
Create the most beautiful Python API for building reports.

Philosophy
JSON is now just serialization.

The Builder creates Report objects.

The Renderer consumes Report objects.

Everything revolves around Report.

Prompt 1: Builder Foundation
Mission
Create a fluent Builder API that constructs Report domain objects.

Background
Sprint 3 established Report as the domain model.

This sprint introduces a Pythonic Builder API.

Architecture Rules
The Builder must not know Flask.

The Builder must not know JSON.

The Builder creates Report objects only.

Objectives
Create package: builder/

Implement:

ReportBuilder

PageBuilder

ObjectBuilder

StyleBuilder

Builder should internally produce Report objects.

Example target API:

Python
builder = ReportBuilder("CBC Report")

report = (
    builder
    .page("A4")
    .text(
        "Complete Blood Count",
        x=50,
        y=40
    )
    .field(
        "patient.name",
        x=50,
        y=90
    )
    .line(
        x=50,
        y=120,
        width=500
    )
    .build()
)
ReportBuilder.build() must return Report.

Do not serialize JSON.

Focus only on object creation.

Document Builder architecture.

Prompt 2: Fluent API
Mission
Improve the fluent API to support method chaining.

Example:

Python
ReportBuilder("Invoice") \
    .page("Letter") \
    .text(...) \
    .field(...) \
    .rectangle(...) \
    .line(...) \
    .page_break() \
    .page("Letter") \
    .text(...) \
    .build()
Builder methods should return the appropriate builder object.

Design for readability over minimal code.

Review naming.

Prefer explicit APIs.

Prompt 3: Builder Convenience
Mission
Create convenience APIs to reduce boilerplate.

Support:

report.title()

report.subtitle()

report.header()

report.footer()

report.margin()

report.landscape()

report.portrait()

report.metadata()

Builder should automatically create a default page when appropriate.

Document examples.

Prompt 4: Styles
Mission
Introduce reusable Style objects.

Example:

Python
title_style = Style(
    font_size=18,
    bold=True
)

builder.text(
    "Laboratory Report",
    style=title_style
)
Allow styles to be reused across objects.

Support style inheritance.

Document architecture.

Prompt 5: Coordinates
Mission
Introduce Position and Size classes to replace raw x/y integers where appropriate.

Example:

Python
Position(50,40)
Size(300,40)

Rectangle(
    position=Position(...),
    size=Size(...)
)
Improve readability.

Avoid unnecessary complexity.

Keep Report model clean.


---- SPRINT 4 refactor ---

Sprint 4 — The Developer Experience

Mission

Build an API so natural that developers don't need to read the documentation to get started.

Prompt 1 — Developer Experience
Sprint 4
"The Developer Experience"

Mission

Design the public API that developers will use every day.

The goal is to make Report itself the primary API.

Do NOT introduce a mandatory ReportBuilder.

Report is the framework.

Architecture Rules

Report is the domain object.

Page belongs to Report.

Objects belong to Page.

Renderer consumes Report.

Serializer converts Report ⇄ JSON.

Flask, CLI, Designer and future adapters should all manipulate Report objects.

Objectives

Review all public classes.

Improve naming.

Improve discoverability.

Reduce unnecessary boilerplate.

Target API

report = Report("Laboratory Report")

page = report.page()

page.text(
    "Laboratory Result",
    x=50,
    y=30
)

page.field(
    "patient.name",
    x=50,
    y=80
)

page.line(
    x=50,
    y=110,
    width=500
)

page.rectangle(
    x=40,
    y=140,
    width=520,
    height=120
)

Developer should never need to understand internal models.

Focus on readability.

Document every public API.

Acceptance Criteria

The API feels natural to Python developers.

Examples are concise.

No Builder class is required.
Prompt 2 — Convenience Methods
Sprint 4

Implement convenience methods on Report and Page.

Report

page()

pages

metadata()

styles()

assets()

validate()

clone()

Page

text()

field()

line()

rectangle()

image() (placeholder)

barcode() (placeholder)

qrcode() (placeholder)

table() (placeholder)

Internally these methods should create the appropriate report objects.

Avoid duplicated logic.

The convenience methods should simply construct objects and add them to the page.

Document each method with examples.
Prompt 3 — Unified Object Model
Sprint 4

Create a unified object model.

Every drawable element should inherit from ReportObject.

Examples

TextObject

FieldObject

RectangleObject

LineObject

ImageObject

BarcodeObject

QRCodeObject

TableObject

The convenience methods should internally instantiate these objects.

Example

page.text(...)

should internally become

page.add(
    TextObject(...)
)

This ensures the Designer, JSON serializer, AI integrations, and developer code all use the same domain objects.

Document the architecture.
Prompt 4 — Page API
Sprint 4

Improve the Page API.

Support:

page.objects

page.find(id)

page.remove(id)

page.clear()

page.add(object)

page.clone()

page.validate()

Support iteration.

Example

for obj in page:

    ...

Pages should behave like Python collections where appropriate.

Keep APIs explicit and readable.
Prompt 5 — Styling System
Sprint 4

Refactor styles.

Create reusable Style objects.

Support inheritance.

Example

title = Style(
    font_size=18,
    bold=True
)

body = Style(
    font_size=11
)

page.text(
    "Title",
    style=title
)

Objects should hold references to Style objects where practical.

Support cloning.

Support serialization.

Document style architecture.
Prompt 6 — Object Factory
Sprint 4

Create an ObjectFactory.

Purpose

Construct report objects consistently.

Support:

create_text()

create_field()

create_line()

create_rectangle()

Future:

create_image()

create_barcode()

create_qrcode()

create_table()

The convenience methods should use ObjectFactory.

The JSON serializer should also use ObjectFactory.

This guarantees every object is created consistently regardless of source.

Document the factory architecture.
Prompt 7 — Public API Tests
Sprint 4

Write developer-focused API tests.

Examples

report = Report("Demo")

page = report.page()

page.text("Hello")

page.field("patient.name")

report.render_html(data)

report.render_pdf(data)

Serialize to JSON.

Deserialize back.

Verify equality.

Verify convenience methods create the same objects as ObjectFactory.

Verify no invalid report is created.

Ensure the API remains intuitive.
Prompt 8 — Architecture Review
Sprint 4

Review the complete architecture.

Questions

Can a beginner build a report without documentation?

Can AI generate reports?

Can the Designer manipulate Report directly?

Can Flask use Report directly?

Can CLI use Report directly?

Can JSON become optional?

Can YAML be added later?

Can XML become a plugin?

Can database storage serialize Report?

Update diagrams.

Update ADRs.

Update README examples.

Document lessons learned.



Sprint 5
"The Canvas"

Mission

Create the first framework-agnostic drag-and-drop designer UI for Slim Report Designer.

Important Architecture Rules

The designer UI must not depend on Flask, Django, FastAPI, or any backend framework.

The designer UI is a frontend package that edits Slim Report JSON.

Framework adapters only host the UI and provide APIs for loading, saving, previewing, and exporting.

Create package:

packages/slim_report_designer_ui/

Structure:

packages/slim_report_designer_ui/
  pyproject.toml
  slim_report_designer_ui/
    __init__.py
    static/
      index.html
      css/
        designer.css
      js/
        designer.js
        canvas.js
        objects.js
        inspector.js
        api.js
        toolbar.js

Designer UI requirements:

1. Layout

Create a full-screen designer interface with:

- top toolbar
- left toolbox
- center canvas/page area
- right property inspector
- bottom status bar

2. Canvas

Create an A4 page canvas using plain HTML/CSS/JavaScript first.

Do not use Fabric.js yet.

Use absolutely positioned div elements for objects.

Show a light grid background.

3. Toolbox

Add buttons:

- Text
- Field
- Line
- Rectangle

4. Object behavior

Support:

- add text object
- add field object
- add line object
- add rectangle object
- select object
- drag object
- basic resize
- delete selected object
- duplicate selected object

5. Property inspector

When selecting an object, show editable properties:

Common:
- id
- type
- x
- y
- width
- height

Text:
- text
- font_size
- bold

Field:
- binding
- font_size
- bold

Rectangle:
- border_width

Line:
- stroke_width

Changing inspector values should update both the canvas and JSON.

6. Template JSON

Maintain one JavaScript template object.

Example:

{
  "version": "0.1",
  "metadata": {
    "name": "Untitled Report"
  },
  "page": {
    "size": "A4",
    "orientation": "portrait",
    "width": 595,
    "height": 842
  },
  "objects": []
}

7. Import / Export

Add buttons:

- Export JSON
- Import JSON
- Copy JSON

Export should download report-template.json.

Import should allow loading JSON file.

Copy should copy JSON to clipboard.

8. API abstraction

Create api.js with functions:

loadTemplate()
saveTemplate(template)
previewTemplate(template)
exportPdf(template)

For now, these can use local mode by default.

If window.SLIM_REPORT_API_BASE exists, call backend endpoints.

9. Pure Python test mode

Add examples/designer_static_server/

Create a simple Python HTTP server example that serves the designer UI without Flask.

10. Flask integration

Update slim_report_flask so it can serve the same designer UI package.

Add route:

GET /report-designer/designer

This should serve the designer index.html.

Add API routes:

GET /report-designer/api/templates/<id>
POST /report-designer/api/templates/<id>
POST /report-designer/api/preview
POST /report-designer/api/export/pdf

These routes should use slim_report_core.

11. Keep it simple

No React.
No Vue.
No build step.
No TypeScript yet.
No Fabric.js yet.

Use plain JavaScript modules so the project remains easy to understand.

Acceptance Criteria

- Designer UI works without Flask using static server.
- Designer UI works inside Flask.
- User can add objects visually.
- User can drag objects.
- User can edit properties.
- User can export JSON.
- Flask can preview/export using the designer JSON.



Sprint 5.1 — Designer UI Polish

Current status:
- Framework-agnostic designer UI works
- Static designer works
- Flask designer works
- Drag/drop works
- Resize works
- Inspector works
- Preview/export PDF works in Flask
- Import/export/copy JSON works

Goal:
Polish the designer UI so it feels like a real report designer, while keeping the architecture simple and framework-agnostic.

Important rules:
- Do not introduce React, Vue, TypeScript, npm, Tailwind, Bootstrap, or a build step.
- Use plain HTML, CSS, and vanilla JavaScript modules only.
- Do not break static mode.
- Do not break Flask mode.
- Do not change the core renderer unless absolutely necessary.
- Do not remove existing functionality.
- Keep the UI package backend-agnostic.

Files to inspect:
- packages/slim_report_designer_ui/slim_report_designer_ui/static/index.html
- packages/slim_report_designer_ui/slim_report_designer_ui/static/css/designer.css
- packages/slim_report_designer_ui/slim_report_designer_ui/static/js/designer.js
- packages/slim_report_designer_ui/slim_report_designer_ui/static/js/canvas.js
- packages/slim_report_designer_ui/slim_report_designer_ui/static/js/inspector.js
- packages/slim_report_designer_ui/slim_report_designer_ui/static/js/toolbar.js

Tasks:

1. Toolbar polish
- Group toolbar actions visually:
  - File: Save, Import JSON, Export JSON, Copy JSON
  - Preview: Preview, Export PDF
  - Edit: Duplicate, Delete
- Keep all existing buttons working.
- Make destructive Delete button visually distinct.
- Improve spacing and alignment.
- Keep the template name visible on the right.

2. Toolbox polish
- Improve left toolbox styling.
- Make toolbox buttons look like report tools.
- Keep tools:
  - Text
  - Field
  - Line
  - Rectangle
- Add small helper text under toolbox title:
  "Click a tool to add it to the page."
- Add active/pressed visual feedback when a tool is clicked if simple.

3. Canvas workspace polish
- Center the page better inside the workspace.
- Add a subtle page shadow.
- Keep the light grid visible but softer.
- Improve scroll behavior.
- Keep horizontal and vertical scrolling working.
- Add visual page boundary.
- Keep page size based on template.page.width and template.page.height.

4. Selection and resize polish
- Improve selected object outline.
- Make resize handle more visible.
- Ensure selected object remains readable.
- Use a small square resize handle in the bottom-right.
- Do not break drag/resize.

5. Inspector polish
- Reorganize inspector into sections:
  - Identity
  - Position
  - Size
  - Content
  - Style
- id and type should appear readonly/disabled.
- x/y/width/height should be grouped in two-column layout if possible.
- For text:
  - text
  - font_size
  - bold
- For field:
  - binding
  - font_size
  - bold
- For rectangle:
  - border_width
- For line:
  - stroke_width
- Show a better empty state when no object is selected:
  "Select an object to edit its properties."

6. Status bar polish
- Show:
  - status message on the left
  - selected object info in the middle
  - object count on the right
- Example:
  Left: Saved
  Middle: Selected: field sex_value
  Right: 110 objects
- Preserve existing status messages like imported, saved, deleted.

7. Dirty state
- Track when the template has unsaved changes.
- Show "Unsaved changes" in the status bar after edits.
- Show "Saved" after Save succeeds.
- Do not block navigation yet.

8. Accessibility/basic UX
- Buttons should have title attributes.
- Inputs should have labels.
- Delete should only run when an object is selected.
- Duplicate should only run when an object is selected.
- Do not throw console errors when no object is selected.

9. Tests/manual checks
- Static designer still loads.
- Flask designer still loads.
- Add Text works.
- Add Field works.
- Drag works.
- Resize works.
- Inspector editing works.
- Duplicate works.
- Delete works.
- Export JSON works.
- Import JSON works.
- Copy JSON works.
- Flask Preview works.
- Flask Export PDF works.

Acceptance criteria:
- UI looks cleaner and less like a debug prototype.
- Existing designer behavior still works.
- No framework dependency is added.
- No build step is added.
- Static mode still works.
- Flask mode still works.


Sprint 5.2 — Style Inspector and Appearance Properties

Current status:
- Framework-agnostic designer UI works.
- Static designer works.
- Flask designer works.
- Drag/drop works.
- Resize works.
- Inspector works.
- UI polish from Sprint 5.1 is implemented.
- Flask preview/export PDF works.
- cerebro_cbc and lab_result templates work.

Goal:
Add more useful appearance/style properties to the designer inspector and make them update:
1. The canvas immediately
2. The template JSON
3. Flask preview/export PDF output as much as the current renderer supports

Important architecture rules:
- Do not introduce React, Vue, TypeScript, npm, Tailwind, Bootstrap, or build steps.
- Use plain HTML, CSS, and vanilla JavaScript modules only.
- Keep the designer UI framework-agnostic.
- Do not break static mode.
- Do not break Flask mode.
- Do not break existing templates.
- Keep backward compatibility with templates that do not have the new style fields.
- Store appearance values in each object style/properties dictionary using simple JSON values.

Files to inspect:
- packages/slim_report_designer_ui/slim_report_designer_ui/static/js/inspector.js
- packages/slim_report_designer_ui/slim_report_designer_ui/static/js/objects.js
- packages/slim_report_designer_ui/slim_report_designer_ui/static/js/canvas.js
- packages/slim_report_designer_ui/slim_report_designer_ui/static/js/designer.js
- packages/slim_report_designer_ui/slim_report_designer_ui/static/css/designer.css
- packages/slim_report_core/src/slim_report_core
- packages/slim_report_flask/src/slim_report_flask/blueprint.py
- examples/flask_app/sample_templates/lab_result.json
- examples/flask_app/sample_templates/cerebro_cbc.json

Tasks:

1. Normalize object style model

Support these style fields where applicable:

Common text/field style:
- font_family
- font_size
- bold
- italic
- underline
- color
- background_color
- align

Rectangle style:
- border_width
- border_color
- background_color

Line style:
- stroke_width
- stroke_color

Default values:
- font_family: Arial
- font_size: 12
- bold: false
- italic: false
- underline: false
- color: #111827
- background_color: transparent
- align: left
- border_width: 1
- border_color: #111827
- stroke_width: 1
- stroke_color: #111827

2. Update objects.js

Ensure objectStyle(object) returns normalized style values without mutating unexpectedly.

It should support both old and new templates.

If an object has style fields directly in object.style, use them.
If old templates use object.properties for some style fields, preserve compatibility.

3. Update inspector.js

Improve the Style section.

For text objects:
- font_family input/select
- font_size number input
- bold checkbox
- italic checkbox
- underline checkbox
- text color picker
- background color picker
- align select: left, center, right

For field objects:
- font_family input/select
- font_size number input
- bold checkbox
- italic checkbox
- underline checkbox
- text color picker
- background color picker
- align select: left, center, right

For rectangle objects:
- border_width number input
- border_color color picker
- background_color color picker

For line objects:
- stroke_width number input
- stroke_color color picker

Use simple native inputs:
- input type="color" for colors
- input type="number" for numeric values
- select for alignment
- checkbox for boolean values

When inspector values change:
- update the selected object JSON
- update the canvas immediately
- mark the template dirty/unsaved
- keep existing x/y/width/height/content behavior working

4. Update canvas rendering

Text and field objects should visually apply:
- font family
- font size
- bold
- italic
- underline
- color
- background color
- text alignment

Rectangle objects should visually apply:
- border width
- border color
- background color

Line objects should visually apply:
- stroke width
- stroke color

Do not break selection outline or resize handle.

Selection outline should remain visible even if object border/background colors change.

5. Update JSON import/export

Exported JSON should include the new style properties only where needed.

Imported JSON should preserve style properties.

Old JSON files without these fields should still load with defaults.

6. Update sample templates carefully

Do not rewrite the whole sample JSON unnecessarily.

If needed, add only minimal style fields to sample objects to demonstrate:
- colored text
- bold text
- centered text
- line color
- rectangle border color

Keep cerebro_cbc visually close to the current design.

7. Update preview/export path

Ensure Flask preview/export receives and preserves the new style fields.

If the core renderer already supports these styles, map them correctly.

If the core renderer does not yet support a style field, add minimal support for:
- text color
- bold
- italic
- underline
- font size
- text align
- background color
- rectangle border color
- rectangle background color
- line stroke color
- line stroke width

Keep changes small and backward-compatible.

8. UI polish for color inputs

Make color controls compact and readable.

Recommended layout:
- label
- color input
- optional text hex value if simple

Do not over-engineer a color palette yet.

9. Manual testing

Test in static mode:
python examples/designer_static_server/serve.py

Confirm:
- Add Text
- Change text color
- Change background color
- Change alignment
- Bold/italic/underline
- Export JSON
- Import JSON
- Style persists

Test in Flask mode:
python examples/flask_app/app.py

Open:
http://127.0.0.1:5000/report-designer/designer?template=cerebro_cbc

Confirm:
- Existing CBC template still loads
- Change selected text color
- Change field color
- Change alignment
- Preview shows style changes
- Export PDF shows style changes where supported

Also test:
http://127.0.0.1:5000/report-designer/designer?template=lab_result

Confirm lab_result still works.

10. Tests

Add or update tests where practical:
- objectStyle returns defaults
- objectStyle preserves explicit style values
- imported template with style fields round-trips
- Flask preview/export accepts templates with new style fields
- Existing lab_result and cerebro_cbc templates still load

Acceptance criteria:
- Inspector has useful appearance controls.
- Canvas updates immediately when style fields change.
- Exported JSON preserves styles.
- Imported JSON restores styles.
- Flask preview/export does not go blank.
- Existing templates still work.
- Static mode still works without backend.
- No new frontend framework or build step is added.




Sprint 5.2b — Designer Icons and Lightweight Version History

Current status:
- Framework-agnostic designer UI works.
- Static designer works.
- Flask designer works.
- Drag/drop works.
- Resize works.
- Inspector works.
- UI polish is implemented.
- Preview/export PDF works in Flask.
- Style inspector work may already be in progress or partially implemented.

Goal:
Add simple built-in icons and lightweight version history to the designer UI without adding frontend dependencies.

Important rules:
- Do not introduce React, Vue, TypeScript, npm, Tailwind, Bootstrap, FontAwesome, CDN icons, or build steps.
- Use plain HTML, CSS, and vanilla JavaScript modules only.
- Keep designer UI framework-agnostic.
- Static mode must work.
- Flask mode must work.
- No database required.
- Do not break existing toolbar actions.
- Do not break existing import/export/preview/pdf behavior.

Files to inspect:
- packages/slim_report_designer_ui/slim_report_designer_ui/static/index.html
- packages/slim_report_designer_ui/slim_report_designer_ui/static/css/designer.css
- packages/slim_report_designer_ui/slim_report_designer_ui/static/js/designer.js
- packages/slim_report_designer_ui/slim_report_designer_ui/static/js/toolbar.js
- packages/slim_report_designer_ui/slim_report_designer_ui/static/js/api.js
- packages/slim_report_designer_ui/slim_report_designer_ui/static/js/inspector.js

Part A — Icons

1. Add a new JS module:
   packages/slim_report_designer_ui/slim_report_designer_ui/static/js/icons.js

2. icons.js should export simple inline SVG icon strings or helper functions for:
   - save
   - preview/eye
   - pdf/file
   - download/export
   - upload/import
   - copy
   - duplicate
   - delete/trash
   - text
   - field
   - line
   - rectangle
   - history
   - restore
   - close

3. Use inline SVG only.
   No external icon packages.
   No CDN.
   No build step.

4. Update toolbar buttons to show icon + accessible label.
   On narrow toolbar space, icons may be shown with short labels or title attributes.

5. Update toolbox buttons to include icons:
   - Text
   - Field
   - Line
   - Rectangle

6. Add CSS for icons:
   - consistent size
   - aligned with button text
   - color follows button text color
   - delete icon should be visually destructive/red

7. All buttons must still have title attributes and accessible text.

Part B — Version History

8. Add a new JS module:
   packages/slim_report_designer_ui/slim_report_designer_ui/static/js/history.js

9. Implement localStorage-backed version history.

10. Use a storage key based on template id/name:
   Example:
   slim_report_designer.history.default
   slim_report_designer.history.cerebro_cbc

11. Add functions:
   - getHistoryKey(templateId)
   - listVersions(templateId)
   - createVersion(templateId, template, label)
   - restoreVersion(templateId, versionId)
   - deleteVersion(templateId, versionId)
   - clearVersions(templateId)

12. A version item should contain:
   - id
   - created_at
   - label
   - object_count
   - template

13. Limit local history to the latest 20 versions per template.

14. Create a snapshot when:
   - Save succeeds
   - User imports JSON, before replacing current template
   - User clicks Create Version manually

15. Do not create snapshots on every drag/drop/resize/property edit.

Part C — Version History UI

16. Add a toolbar button:
   - Version History
   - icon: history
   - title: View Version History

17. Add a simple modal or side panel for version history.

18. Version History UI should show:
   - created date/time
   - label
   - object count
   - Restore button
   - Delete button

19. Add button:
   - Create Version
   This stores the current template immediately with label "Manual version".

20. Add button:
   - Clear History
   This asks for confirm() before clearing local history.

21. Restore behavior:
   - Before restoring, create a snapshot of the current template labeled "Before restore".
   - Replace current designer template with selected historical version.
   - Re-render canvas and inspector.
   - Mark template as unsaved.
   - Show status message: "Restored version from <date>"

22. Delete version behavior:
   - Remove selected version from local history.
   - Refresh history UI.
   - Do not affect current template.

23. Clear history behavior:
   - Clear local history for current template only.
   - Refresh history UI.
   - Show status message.

Part D — Template id awareness

24. Determine template id from:
   - URL query parameter ?template=cerebro_cbc
   - fallback to template.metadata.name
   - fallback to "default"

25. Use this template id for version history key.

26. Do not require backend support for version history yet.

Part E — Flask compatibility

27. Flask designer should still work.
28. Static designer should still work.
29. Version history must work in both modes because it is localStorage-based.
30. Preview and Export PDF behavior should not change.

Part F — Manual test

Test static mode:
python examples/designer_static_server/serve.py

Confirm:
- Icons appear in toolbar/toolbox
- Add Text works
- Drag works
- Resize works
- Inspector works
- Create Version works
- View Version History works
- Restore version works
- Delete version works
- Clear history works
- Import JSON creates "Before import" version
- Export JSON still works
- Copy JSON still works

Test Flask mode:
python examples/flask_app/app.py

Open:
http://127.0.0.1:5000/report-designer/designer?template=cerebro_cbc

Confirm:
- Icons appear
- Existing CBC template loads
- Version history key is based on cerebro_cbc
- Create Version works
- Restore works
- Preview still works
- Export PDF still works

Acceptance criteria:
- Designer UI has built-in icons without external dependencies.
- Version history works locally in static and Flask mode.
- Existing designer actions still work.
- No new frontend framework is added.
- No build step is added.



---------------------------------------------



Sprint 5.5 — Multi-select, Align, Distribute, and Layer Controls

Current status:
- Framework-agnostic designer UI works.
- Static designer works.
- Flask designer works.
- Drag/drop works.
- Resize works.
- Style inspector works.
- Icons and local version history work.
- Page properties work.
- Image object support works.
- Zoom, grid, snap, undo/redo work.
- Inspector focus issue is fixed.
- Preview/export PDF works in Flask.

Goal:
Add precision layout tools:
- multi-select
- align selected objects
- distribute selected objects
- layer ordering
- lock/unlock objects

Important rules:
- Do not introduce React, Vue, TypeScript, npm, Tailwind, Bootstrap, CDN, or build steps.
- Use plain HTML, CSS, and vanilla JavaScript modules only.
- Keep designer UI framework-agnostic.
- Static mode must work.
- Flask mode must work.
- Do not break existing templates.
- Do not break preview/export PDF.
- Do not break undo/redo.
- Do not break drag/resize/zoom/snap.

Files to inspect:
- packages/slim_report_designer_ui/slim_report_designer_ui/static/js/designer.js
- packages/slim_report_designer_ui/slim_report_designer_ui/static/js/canvas.js
- packages/slim_report_designer_ui/slim_report_designer_ui/static/js/toolbar.js
- packages/slim_report_designer_ui/slim_report_designer_ui/static/js/inspector.js
- packages/slim_report_designer_ui/slim_report_designer_ui/static/js/objects.js
- packages/slim_report_designer_ui/slim_report_designer_ui/static/css/designer.css
- packages/slim_report_designer_ui/slim_report_designer_ui/static/index.html

Tasks:

1. Multi-select state

Replace single selected id with support for:
- selectedIds array
- primarySelectedId

Behavior:
- Click object selects only that object.
- Shift + click toggles object in selection.
- Ctrl/Cmd + click also toggles object in selection.
- Clicking empty canvas clears selection.
- Existing single-object inspector still works when one object is selected.
- When multiple objects are selected, inspector shows multi-selection summary.

2. Multi-select visual UI

Selected objects should show selected outline.
Primary selected object may have stronger outline.
Show group bounding box around multiple selected objects if practical.

3. Drag multiple selected objects

When multiple objects are selected:
- dragging any selected object moves all selected objects together.
- movement respects zoom.
- movement respects snap-to-grid if enabled.
- objects remain inside page as much as possible.
- operation is undoable.

4. Resize behavior

For now, resize only primary selected object.
Do not implement group resize yet.
When multiple selected, hide individual resize handles except primary selected object.

5. Multi-selection inspector

When multiple objects are selected, show:
- number of selected objects
- selected object types count
- common actions:
  - align left
  - align center
  - align right
  - align top
  - align middle
  - align bottom
  - distribute horizontal
  - distribute vertical
  - lock selected
  - unlock selected
  - delete selected
  - duplicate selected

6. Align tools

Add toolbar buttons and/or inspector buttons for:
- Align left
- Align horizontal center
- Align right
- Align top
- Align vertical middle
- Align bottom

Behavior:
- If multiple selected, align relative to the primary selected object or selection bounds.
Recommended:
  - align left uses minimum x among selected
  - align right uses maximum right edge
  - align center uses selection center
  - align top uses minimum y
  - align bottom uses maximum bottom edge
  - align middle uses selection middle
- Changes are undoable.

7. Distribute tools

Add:
- Distribute horizontal
- Distribute vertical

Behavior:
- Requires at least 3 selected objects.
- Sort objects by x or y.
- Keep first and last fixed.
- Evenly distribute middle objects.
- Changes are undoable.

8. Layer ordering

Add object order controls:
- Bring forward
- Send backward
- Bring to front
- Send to back

Behavior:
- Use order in template.objects array as z-order.
- Later objects render above earlier objects.
- Works for one or multiple selected objects.
- Changes are undoable.
- Canvas render should respect object array order.

9. Lock/unlock objects

Add object property:
- locked: true/false

Behavior:
- Locked objects can be selected.
- Locked objects cannot be dragged/resized.
- Inspector should show locked state.
- Toolbar/inspector should allow lock/unlock.
- Locked objects should have subtle lock visual indicator.
- Delete should still require explicit action; okay to allow delete locked only after confirm, or block delete locked.

10. Duplicate/delete multi-selected

- Duplicate selected duplicates all selected objects.
- Duplicates should keep relative positions and offset by 10px or grid size.
- Delete selected deletes all selected objects.
- Operations are undoable.

11. Keyboard support

- Delete removes selected objects.
- Arrow keys move selected objects by 1px.
- Shift + Arrow moves selected objects by grid size.
- Ctrl/Cmd + A selects all objects.
- Escape clears selection.
- Do not trigger shortcuts while typing in inspector inputs.

12. Toolbar state

Disable align/distribute/layer buttons when not applicable.
Example:
- align requires at least 2 selected
- distribute requires at least 3 selected
- layer requires at least 1 selected
- delete/duplicate requires at least 1 selected

13. Status bar

Update selected info:
- no selection: Page selected
- one selection: Selected: text text_1
- multi-selection: Selected: 5 objects

14. Undo/redo integration

All new operations must push undo snapshots:
- multi-drag
- align
- distribute
- layer changes
- lock/unlock
- duplicate multi
- delete multi

15. Manual tests

Static mode:
python examples/designer_static_server/serve.py

Test:
- Add 5 text objects
- Shift-click multi-select
- Drag selected group
- Align left/top/center
- Distribute horizontal/vertical
- Bring front/send back
- Lock object
- Try drag locked object
- Unlock object
- Duplicate selected group
- Delete selected group
- Undo/redo every operation
- Ctrl+A selects all
- Escape clears selection

Flask mode:
python examples/flask_app/app.py

Open:
http://127.0.0.1:5000/report-designer/designer?template=cerebro_cbc

Test:
- Multi-select existing CBC objects
- Align selected labels
- Move selected group
- Preview still works
- Export PDF still works

Acceptance criteria:
- Multi-select works.
- Multi-object drag works.
- Align tools work.
- Distribute tools work.
- Layer controls work.
- Lock/unlock works.
- Undo/redo works for new operations.
- Static mode still works.
- Flask mode still works.
- Preview/export PDF still works.