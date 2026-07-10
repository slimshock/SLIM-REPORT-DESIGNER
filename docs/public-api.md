# Public API

`Report` is the primary developer API for Slim Report Designer.

Developers should be able to create useful reports without constructing internal template
dictionaries or using a builder.

## Report

Create a report with a title:

```python
from slim_report_core import Report

report = Report("Laboratory Report")
```

`Report` owns pages, objects, styles, metadata, assets, validation, rendering, events, and cloning.

Common methods:

- `report.page()` returns the first page.
- `report.pages()` returns the report page collection.
- `report.metadata(...)` updates and returns report metadata.
- `report.styles(...)` returns or updates named styles.
- `report.assets()` returns the asset collection.
- `report.new_page(...)` adds and returns a page.
- `report.add_page(...)` adds and returns a page.
- `report.render_html(data)` renders HTML.
- `report.render_pdf(data)` renders PDF bytes.
- `report.validate()` returns structured validation results.
- `report.find(id_or_predicate)` finds objects.
- `report.fields()` returns field objects.
- `report.text_objects()` returns text objects.
- `report.clone()` returns a deep clone.

## Page

Pages belong to reports. Objects are added through pages:

```python
report = Report("Laboratory Report")
page = report.page()

page.text("Laboratory Result", x=50, y=30)
page.field("patient.name", x=50, y=80)
page.line(x=50, y=110, width=500)
page.rectangle(x=40, y=140, width=520, height=120)
```

The page helpers instantiate concrete `ReportObject` subclasses internally. For example,
`page.text(...)` is equivalent to `page.add(TextObject(...))`.

Each object added through a page receives `object.properties["page_id"]`.

Common page methods:

- `page.text(...)`
- `page.field(...)`
- `page.line(...)`
- `page.rectangle(...)`
- `page.image(...)`
- `page.barcode(...)`
- `page.qrcode(...)`
- `page.table(...)`
- `page.add(...)`
- `page.find(...)`
- `page.remove(...)`
- `page.clear()`
- `page.clone()`
- `page.validate()`
- `page.object(...)`
- `page.objects`

Use `page.add(...)` when you already have a concrete domain object:

```python
from slim_report_core import TextObject

page.add(TextObject("Manual title", x=50, y=30))
```

Use `page.object(...)` only for custom object types that do not yet have a concrete class.

Pages also behave like small Python collections of their objects:

```python
for obj in page:
    print(obj.id)

title = page.find("title")
removed = page.remove("old_title")
page.clear()
```

`len(page)`, `page[0]`, object membership, and id membership are supported for concise inspection.

## Report Methods

### `report.page()`

Returns the first page and creates one when needed:

```python
page = report.page()
```

### `report.pages`

Use as a collection or call it explicitly:

```python
all_pages = report.pages
same_pages = report.pages()
```

### `report.metadata(...)`

Updates metadata and returns the metadata object:

```python
report.metadata(
    title="Laboratory Report",
    subtitle="CBC",
    author="Lab Team",
)
```

### `report.styles(...)`

Returns the style collection when called without arguments, or creates/updates a named style:

```python
report.styles("heading", font_size=18, bold=True)
heading_style = report.styles["heading"]
```

### `report.assets`

Use as a collection or call it explicitly:

```python
report.add_asset({"id": "logo", "type": "image", "source": "logo.png"})
assets = report.assets()
```

### `report.validate()`

Returns structured validation errors:

```python
result = report.validate()
```

### `report.clone()`

Returns a deep clone:

```python
draft = report.clone()
same_ids = report.clone(new_ids=False)
```

## Page Methods

### `page.text(...)`

Adds a text object:

```python
page.text("Laboratory Result", x=50, y=30)
```

### `page.field(...)`

Adds a data-bound field object:

```python
page.field("patient.name", x=50, y=80)
```

### `page.line(...)`

Adds a line object:

```python
page.line(x=50, y=110, width=500)
```

### `page.rectangle(...)`

Adds a rectangle object:

```python
page.rectangle(x=40, y=140, width=520, height=120)
```

### `page.image(...)`

Adds an image object:

```python
page.image("logo.png", x=40, y=40, width=120, height=60)
```

### `page.barcode(...)`

Adds a barcode object. HTML preview and PDF export render a barcode visual and optional text label:

```python
page.barcode("ABC123", x=40, y=120, width=200, height=60)
```

### `page.qrcode(...)`

Adds a QR code object. HTML preview and PDF export render a deterministic QR-style visual:

```python
page.qrcode("https://example.test", x=40, y=200, width=100, height=100)
```

### `page.table(...)`

Adds a basic array-bound table object:

```python
page.table(
    data_path="results",
    x=40,
    y=320,
    width=520,
    height=200,
    columns=[{"label": "Test", "binding": "test"}],
)
```

### `page.add(...)`

Adds an existing concrete report object:

```python
from slim_report_core import TextObject

page.add(TextObject("Manual title", x=50, y=30))
```

### `page.find(...)`

Finds an object on this page by id:

```python
title = page.find("title")
```

### `page.remove(...)`

Removes an object from this page by id and returns it:

```python
removed = page.remove("title")
```

### `page.clear()`

Removes every object from this page:

```python
page.clear()
```

### `page.validate()`

Returns structured validation errors for the page and its objects:

```python
result = page.validate()
```

### `page.object(...)`

Adds a custom object type:

```python
page.object("custom", x=40, y=40, width=100, height=40, value="demo")
```

## Geometry

Raw coordinates are concise:

```python
page.text("Laboratory Result", x=50, y=30, width=300, height=40)
```

Use `Position` and `Size` when explicit geometry is clearer:

```python
from slim_report_core import Position, Size

page.rectangle(
    position=Position(40, 140),
    size=Size(520, 120),
)
```

## Styles

Styles are reusable domain objects:

```python
from slim_report_core import Style

title_style = Style(font_size=18, bold=True)
page.text("Laboratory Result", x=50, y=30, style=title_style)
```

Objects keep direct `Style` references when no local overrides are supplied. Use keyword overrides
to create an inherited child style for one object:

```python
body = Style(font_family="Helvetica", font_size=11)
page.text("Laboratory Result", x=50, y=30, style=body, font_size=18, bold=True)
```

Styles support inheritance:

```python
base_style = Style(font_family="Helvetica", font_size=12)
title_style = base_style.inherit(font_size=18, bold=True)
```

## Serialization

Serialization is explicit:

```python
from slim_report_core.serialization import JSONSerializer

serializer = JSONSerializer()
serializer.save(report, "template.json")
loaded = serializer.load("template.json")
```

`Report` does not expose JSON load/save methods. JSON remains one persistence format.

## Rendering

Renderers consume `Report`:

```python
html = report.render_html(data)
pdf_bytes = report.render_pdf(data)
```

Framework adapters, CLI commands, designers, and future integrations should manipulate `Report`
objects, then render or serialize at the boundary.

## Template Normalization

Use `normalize_template` when accepting template dictionaries from designer clients or examples:

```python
from slim_report_core import normalize_template

template = normalize_template({
    "metadata": {"name": "Lab Report"},
    "page": {},
    "objects": [],
    "bands": [],
})
```

It returns a new mapping with serializer defaults such as `version`, `metadata.title`,
`metadata.name`, `page.unit`, `assets`, `objects`, and `bands`.

## Builder

`ReportBuilder` remains available as an optional convenience API. It is not required for normal
report creation.

## SQL Validation

Use `SQLValidator` with a dialect to validate report queries without connecting to a database:

```python
from slim_report_core import MySQLDialect, SQLValidator

result = SQLValidator(MySQLDialect()).validate(
    "SELECT * FROM patients WHERE id=:patient_id"
)
```

See [SQL Validation](sql-validation.md) for supported statements, parameter syntax, normalization,
policies, dataset checks, and the database-permission security boundary.

## MySQL Connection Provider

Install the optional driver with `pip install "slim-report-core[mysql]"`, then register the provider:

```python
from slim_report_core import DataSourceProviderRegistry, MySQLDataSourceProvider

registry = DataSourceProviderRegistry()
registry.register(MySQLDataSourceProvider())
provider = registry.get("mysql")
result = provider.test_connection(data_source)
```

Use `provider.connection(data_source)` as a context manager when a later application service needs a
configured connection. Sprint 7.3 does not execute dataset SQL. See
[MySQL Data-Source Provider](mysql-data-source-provider.md) for the lifecycle, failure contract,
read-only policy, compatibility limitations, and security model.
