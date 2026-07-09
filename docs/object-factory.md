# Object Factory

`ObjectFactory` is the single construction point for drawable report objects.

It creates the concrete `ReportObject` subclasses used by developer code, page helpers,
serializers, designers, adapters, and future AI integrations.

## Supported Constructors

```python
from slim_report_core import ObjectFactory, Style

factory = ObjectFactory()
title_style = Style(font_size=18, bold=True)

title = factory.create_text("Laboratory Result", x=50, y=30, style=title_style)
patient = factory.create_field("patient.name", x=50, y=80)
line = factory.create_line(x=50, y=110, width=500)
box = factory.create_rectangle(x=40, y=140, width=520, height=120)
```

Image, barcode, QR code, and basic table construction are supported:

```python
factory.create_image("logo.png")
factory.create_barcode("ABC123")
factory.create_qrcode("https://example.test")
factory.create_table(binding="results")
```

`create_image(...)` creates a renderable image object. `create_barcode(...)` and `create_qrcode(...)` create renderable label/code objects with binding or literal value support. `create_table(...)` creates a basic array-bound table object. Advanced table rendering is future work.

## Page Helpers

Page helpers delegate to the factory:

```python
page.text("Title")
```

is equivalent to:

```python
page.add(ObjectFactory().create_text("Title"))
```

`page.add(...)` remains the explicit path for adding an already-created domain object.

## Serialization

`JSONSerializer` uses `ObjectFactory.create_from_dict(...)` when loading object mappings:

```text
JSON object mapping
    |
    v
ObjectFactory.create_from_dict(...)
    |
    v
TextObject / FieldObject / LineObject / RectangleObject / ...
```

`Object.from_dict(...)` delegates to the same factory for compatibility.

## Architecture Rule

New drawable object types should be added to `ObjectFactory` first. After that, page helpers,
serializers, designers, and integrations should call the factory rather than constructing a
parallel object shape.
