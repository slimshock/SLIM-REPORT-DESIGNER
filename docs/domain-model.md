# Report Domain Model

`Report` is the central domain model in Slim Report Designer.

JSON is a persistence format. It is not the domain model.

## Core Rule

`slim_report_core` owns report structure and rendering inputs. It must remain framework agnostic and must not import Flask, Django, FastAPI, SQLAlchemy, or web framework code.

Framework adapters load, store, and pass reports to the core. They do not implement rendering logic.

## Report

`Report` is the daily developer API:

```python
from slim_report_core import Report

report = Report("Laboratory Report")
page = report.page()

page.text("Laboratory Result", x=50, y=30)
page.field("patient.name", x=50, y=80)
page.line(x=50, y=110, width=500)
page.rectangle(x=40, y=140, width=520, height=120)
page.image("logo.png", x=40, y=40, width=120, height=60)
```

Pages behave like explicit collections of their page-owned objects:

```python
for obj in page:
    ...

title = page.find("title")
page.remove("old_title")
page.clear()
result = page.validate()
```

`Report` also exposes the primary report state:

```python
report.version
report.metadata
report.pages
report.page
report.objects
report.bands
report.layers
report.styles
report.assets
```

`report.page` returns the first page for single-page compatibility, and `report.page()` works as
the readable creation API. New code should prefer `report.pages` when working with page
collections.

## Domain Objects

The domain model includes:

- `Metadata`: title, description, author, tags, and custom metadata
- `Page`: page size, unit, orientation, and margins
- `Margin`: top, right, bottom, and left margin values
- `Position`: top-left object coordinates
- `Size`: object width and height
- `Object` / `ReportObject`: base class for every drawable report object
- `TextObject`, `FieldObject`, `LineObject`, `RectangleObject`, `ImageObject`: renderable concrete objects
- `BarcodeObject`, `QRCodeObject`, `TableObject`: renderable concrete objects for barcode/QR labels and basic tabular data
- `Style`: reusable named or inline style values with optional inheritance
- `Binding`: data binding expression for field objects
- `Band`: layout grouping primitive
- `Layer`: optional visual grouping primitive
- `Asset`: external or embedded report asset reference

`ReportObject` remains the public alias for the base object class. New drawable types should inherit
from it rather than using parallel dictionaries or adapter-specific shapes.

Page convenience methods create concrete object classes and add them through one path:

```python
from slim_report_core import TextObject

page.text("Laboratory Result", x=50, y=30)
page.add(TextObject("Laboratory Result", x=50, y=30))
```

Both calls produce the same domain object shape. Designer code, JSON serializers, AI integrations,
CLI commands, Flask adapters, and developer code should all target these domain objects.

Legacy aliases such as `ReportPage` and `ReportAsset` remain available for compatibility, but the concise names are preferred for new domain code.

## Styles

`Style` supports reusable style objects:

```python
from slim_report_core import Style

title_style = Style(font_size=18, bold=True)
```

Styles can inherit from another style:

```python
base_style = Style(font_family="Helvetica", font_size=12)
title_style = base_style.inherit(font_size=18, bold=True)
```

`style.values` stores local values. `style.resolved_values()` returns inherited parent values plus
local overrides. Objects can hold direct references to reusable `Style` instances; object-level
keyword overrides create inherited child styles. Renderers, validation, and serializers use resolved
values.

## Report API

```python
from slim_report_core import Asset, Report

report = Report("Laboratory Result")
page = report.page()
page.text("LABORATORY RESULT", x=50, y=40, id="title")
report.add_asset(Asset(id="logo", type="image", source="logo.png"))

found = report.find_object("title")
same_object = report.find("title")
first_text = report.find(lambda obj: obj.type == "text")
text_objects = report.text_objects()
copy_for_editing = report.clone()
```

## Geometry

Objects support both raw coordinates and readable value objects:

```python
from slim_report_core import Object, Position, Size

box = Object(
    id="result_box",
    type="rectangle",
    position=Position(50, 150),
    size=Size(500, 100),
)
```

`box.position` and `box.size` stay synchronized with `box.x`, `box.y`, `box.width`, and
`box.height`. Serializers continue to emit the existing coordinate fields.

`image()` creates a renderable image object. `barcode()`, `qrcode()`, and `table()` create renderable
domain objects. Current HTML/PDF rendering supports text, field, line, rectangle, image, barcode,
QR code, table, bands, and repeating Detail rows.

Supported helpers:

- `page()`
- `new_page()`
- `add_page()`
- `remove_page()`
- `add_object()`
- `remove_object()`
- `find_object()`
- `get_object()` compatibility alias
- `find()`
- `find_by_name()`
- `objects()`
- `text_objects()`
- `fields()`
- `images()`
- `tables()`
- `add_asset()`
- `clone()`
- `copy()`
- `validate()`
- `on()`
- `off()`

`clone()` and `copy()` return deep copies so callers can safely mutate them without changing the original report.

By default, `clone()` creates new ids:

```python
cloned = report.clone()
```

Preserve ids only when requested:

```python
template_copy = report.clone(new_ids=False)
```

`report.copy()` preserves ids for compatibility. `report.clone(share_assets=True)` reuses asset objects instead of cloning them.

## Validation

`Report.validate()` returns structured errors and does not raise exceptions for normal validation failures:

```python
result = report.validate()

if not result.is_valid:
    for error in result.errors:
        print(error.path, error.code, error.message)
```

Validation checks pages, objects, unique ids, bindings, styles, and assets.

## Querying

`report.objects` is list-like and callable:

```python
all_objects = report.objects()
visible_fields = report.fields(lambda obj: obj.visible)
header = report.find_by_name("Header")
```

`find()` and the type helpers also accept predicates for concise object queries.

## Events

Reports expose framework-independent events:

```python
def audit(event):
    print(event.name, event.payload)

report.on("before_render", audit)
report.on("object_added", audit)
```

Supported events include render/export lifecycle events and object/page mutation events.

## Serialization

Persistence conversion lives at the edges. JSON is currently implemented by `JSONSerializer`:

```python
from slim_report_core.serialization import JSONSerializer

serializer = JSONSerializer()
report = serializer.load_mapping(template_json)
template_json = serializer.dump_mapping(report)
```

`Report` does not expose JSON load/save helpers. Keep JSON at the serializer boundary.

The JSON shape remains compatible with existing templates:

```json
{
  "version": "1.0",
  "metadata": {},
  "page": {},
  "objects": [],
  "bands": [],
  "assets": []
}
```

Optional domain collections such as `pages`, `layers`, and `styles` are serialized when present.

## Rendering Boundary

Renderers accept `Report` directly:

```python
from slim_report_core import render_html, render_pdf

html = render_html(report, data)
pdf = render_pdf(report, data)
```

Do not pass JSON dictionaries to renderers. Use `JSONSerializer` at the persistence boundary, then render the resulting `Report`.
