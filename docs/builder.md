# Builder API

The Builder API is an optional convenience layer that creates `Report` domain objects directly.

Developers do not need a builder for normal report creation. The primary API is:

```python
from slim_report_core import Report

report = Report("Laboratory Report")
page = report.page()
page.text("Laboratory Result", x=50, y=30)
```

It does not load JSON, write JSON, render reports, or know about Flask, Django, FastAPI, CLI
commands, storage, or HTTP requests. Persistence remains the responsibility of serializers.

## Flow

```text
ReportBuilder
    |
    v
Report
    |
    +-- Report.validate()
    +-- render_html(report, data)
    +-- render_pdf(report, data)
    +-- JSONSerializer.save(report, path)
```

## Example

```python
from slim_report_core import ReportBuilder

report = (
    ReportBuilder("CBC Report")
    .page("A4")
    .text("Complete Blood Count", x=50, y=40, font_size=18, bold=True)
    .field("patient.name", x=50, y=90)
    .line(x=50, y=120, width=500)
    .build()
)

result = report.validate()
html = report.render_html({"patient": {"name": "JUAN DELA CRUZ"}})
```

`ReportBuilder.build()` returns `Report`.

## Convenience API

Use convenience methods when the report follows common document structure:

```python
from slim_report_core import ReportBuilder

report = (
    ReportBuilder()
    .metadata(
        title="Invoice",
        subtitle="July Billing",
        author="Billing Team",
    )
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

Convenience methods stay explicit:

- `metadata()` updates report metadata only.
- `title()` adds a title text object and sets `report.metadata.title`.
- `subtitle()` adds a subtitle text object and stores `metadata.custom["subtitle"]`.
- `header()` and `footer()` add text objects with `role` properties.
- `margin()`, `landscape()`, and `portrait()` configure the current page.

`ReportBuilder` creates a default Letter page in pixel units, so simple reports do not need an
initial `.page(...)` call. Calling `.page("A4")` or `.page("Letter")` still configures the current
page explicitly.

## Reusable Styles

Builder methods accept reusable `Style` objects:

```python
from slim_report_core import ReportBuilder, Style

title_style = Style(font_size=18, bold=True)

report = (
    ReportBuilder("Laboratory Report")
    .text("Laboratory Report", x=50, y=40, style=title_style)
    .text("Final Result", x=50, y=80, style=title_style)
    .build()
)
```

Styles can inherit from other styles:

```python
base_style = Style(font_family="Helvetica", font_size=12, color="#111111")
title_style = base_style.inherit(font_size=18, bold=True)

report = ReportBuilder("Laboratory Report").text("Laboratory Report", style=title_style).build()
```

When no object-level overrides are supplied, builder-created objects keep the passed `Style`
reference. If overrides or default helper styles are involved, the builder creates an inherited or
merged style for that object.

## Geometry Value Objects

Builder methods accept `Position` and `Size` for readable layout code:

```python
from slim_report_core import Position, ReportBuilder, Size

report = (
    ReportBuilder("Laboratory Report")
    .text("Laboratory Report", position=Position(50, 40), size=Size(300, 30))
    .field("patient.name", position=Position(50, 90), size=Size(300, 20))
    .rectangle(position=Position(50, 150), size=Size(500, 100))
    .build()
)
```

Raw `x`, `y`, `width`, and `height` remain valid for concise calls.

## Multi-page Chaining

`page()` configures the current page. `page_break()` starts a new current page, so following
objects are associated with that page.

```python
from slim_report_core import ReportBuilder

report = (
    ReportBuilder("Invoice")
    .page("Letter")
    .text("Invoice", x=50, y=40)
    .field("customer.name", x=50, y=80)
    .rectangle(x=45, y=110, width=500, height=120)
    .line(x=45, y=250, width=500)
    .page_break()
    .page("Letter")
    .text("Terms", x=50, y=40)
    .build()
)
```

For code that should read more explicitly, use `new_page()`:

```python
report = (
    ReportBuilder("Invoice")
    .page("Letter", id="cover")
    .text("Invoice", x=50, y=40)
    .new_page("Letter", id="terms")
    .text("Terms", x=50, y=40)
    .build()
)
```

Objects created by `ReportBuilder` store the current page id in `object.properties["page_id"]`.
This gives future renderers and designers a stable page association without coupling the builder
to JSON or a web framework.

## Builder Classes

- `ReportBuilder` creates and configures a `Report`.
- `PageBuilder` creates or configures a `Page`.
- `ObjectBuilder` creates positioned `Object` instances.
- `StyleBuilder` creates `Style` instances.

The high-level `ReportBuilder` methods return the same builder so simple reports can be
created as one fluent chain:

```python
report = (
    ReportBuilder("Result")
    .page("Letter")
    .text("Result", x=40, y=40)
    .field("result.HGB", x=40, y=80)
    .rectangle(x=35, y=70, width=300, height=80)
    .build()
)
```

Lower-level builders are available when another layer needs finer control:

```python
from slim_report_core import ObjectBuilder, StyleBuilder

style = StyleBuilder().font_size(12).bold().build()

field = (
    ObjectBuilder("field", object_id="patient_name", x=50, y=90, width=300, height=20)
    .binding("patient.name")
    .style(style)
    .build()
)
```

## Persistence

Builder output is persisted by serializers:

```python
from slim_report_core import ReportBuilder
from slim_report_core.serialization import JSONSerializer

report = ReportBuilder("CBC Report").page("A4").text("CBC", x=50, y=40).build()
JSONSerializer().save(report, "template.json")
```

This keeps JSON as one persistence format instead of a dependency of the builder or report
domain model.
