# Styles

`Style` is a reusable domain object in `slim_report_core`.

Styles belong to the core domain model. They do not know about JSON, Flask, HTML, PDF, or a
specific renderer.

## Reusable Styles

Create a style once and reuse it across report objects:

```python
from slim_report_core import Report, Style

title_style = Style(font_size=18, bold=True)

report = Report("Laboratory Report")
page = report.page()

page.text("Laboratory Report", x=50, y=40, style=title_style)
page.text("Final Result", x=50, y=80, style=title_style)
```

When a `Style` object is passed directly, report objects keep that style reference. This allows
shared style updates while the report is being built:

```python
title_style.values["color"] = "#111111"
```

Both text objects now resolve the new color. Use `style.clone()` when an object needs an
independent copy.

Existing dictionary-style construction remains supported:

```python
style = Style({"font_size": 12, "color": "#111111"})
```

The preferred Python API is keyword-based:

```python
style = Style(font_size=12, color="#111111")
```

## Inheritance

Styles can inherit from another style:

```python
base_style = Style(font_family="Helvetica", font_size=12, color="#111111")
title_style = base_style.inherit(font_size=18, bold=True)

assert title_style.resolved_values() == {
    "font_family": "Helvetica",
    "font_size": 18,
    "color": "#111111",
    "bold": True,
}
```

Child values override parent values. `style.values` stores only local values. Use
`style.resolved_values()` or `style.to_dict()` when rendering, validating, or exporting a fully
resolved style.

Object-level style keyword overrides create an inherited child style:

```python
body = Style(font_family="Helvetica", font_size=11)
title = page.text("Title", style=body, font_size=18, bold=True)

assert title.style.parent is body
```

This keeps the reusable base style intact while allowing the object to override selected values.

## Named Styles

Reports can store reusable named styles:

```python
report = (
    ReportBuilder("Styled")
    .style("base", font_family="Helvetica", font_size=10)
    .build()
)

title_style = report.styles["base"].inherit(font_size=18, bold=True)
```

Named styles are regular `Style` objects stored in `report.styles`.

## Rendering Boundary

Rendering consumes resolved style values:

```text
Style(parent + local values)
    |
    v
resolved_values()
    |
    v
HTML/PDF renderer
```

This keeps inheritance in the domain model. Renderers do not need to know whether a style value
came from a base style or a child override.

## Cloning

`Style.clone()` deep clones local values and the parent style chain:

```python
draft_style = title_style.clone()
```

Object cloning also clones the object's style, so cloned reports can be edited without mutating the
source report's styles.

## Serialization

JSON serialization persists resolved style dictionaries for compatibility:

```json
{
  "font_family": "Helvetica",
  "font_size": 18,
  "bold": true
}
```

Loading JSON converts those dictionaries back into `Style` domain objects. The current JSON format
does not preserve parent identity; inheritance is a runtime domain concern. Future serializers can
preserve richer inheritance metadata, but rendering and validation should continue to depend on the
`Style` API rather than a persistence format.
