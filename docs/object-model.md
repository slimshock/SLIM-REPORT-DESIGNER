# Object Model

Slim Report Designer uses one unified domain object model for drawable report elements.

Every drawable element inherits from `ReportObject`:

```text
ReportObject
  TextObject
  FieldObject
  LineObject
  RectangleObject
  ImageObject
  BarcodeObject
  QRCodeObject
  TableObject
```

`ReportObject` is the shared base for designer code, serializers, renderers, adapters, AI
integrations, and developer code.

## Concrete Objects

Use concrete objects directly when needed:

```python
from slim_report_core import Report, TextObject

report = Report("Laboratory Report")
page = report.page()

page.add(TextObject("Laboratory Result", x=50, y=30))
```

Most application code should use the page convenience methods:

```python
page.text("Laboratory Result", x=50, y=30)
page.field("patient.name", x=50, y=80)
page.line(x=50, y=110, width=500)
page.rectangle(x=40, y=140, width=520, height=120)
```

Internally, those methods use `ObjectFactory` and call `page.add(...)`:

```python
page.add(TextObject("Laboratory Result", x=50, y=30))
```

## Placeholder Objects

The following concrete objects exist as domain placeholders for future renderer support:

```python
page.image("logo.png", x=40, y=40, width=120, height=60)
page.barcode("ABC123", x=40, y=120, width=200, height=60)
page.qrcode("https://example.test", x=40, y=200, width=100, height=100)
page.table(binding="results", x=40, y=320, width=520, height=200)
```

They create `ImageObject`, `BarcodeObject`, `QRCodeObject`, and `TableObject` domain objects. HTML
and PDF rendering for these placeholders is intentionally not implemented yet.

## Serialization

`ObjectFactory.create_from_dict(...)` dispatches JSON-compatible mappings into concrete object
classes. `Object.from_dict(...)` delegates to the same factory for compatibility:

```python
obj = ReportObject.from_dict({
    "id": "title",
    "type": "text",
    "text": "Laboratory Result",
})

assert isinstance(obj, TextObject)
```

Serializers still emit the stable object shape with `type`, `x`, `y`, `width`, `height`, and
properties. The concrete Python class is a domain concern, not a JSON schema requirement.

## Cloning

Object cloning preserves concrete type:

```python
title = TextObject("Laboratory Result", id="title")
clone = title.clone(new_ids=False)

assert isinstance(clone, TextObject)
```

## Architecture Rule

New object types should be added as `ReportObject` subclasses first. Page convenience methods,
serializers, designers, and AI integrations should target those classes rather than inventing
parallel object shapes.
