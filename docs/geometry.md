# Geometry

`Position` and `Size` are small domain value objects for positioned report objects.

They improve readability in Python code without changing the renderer or serialized coordinate model.
Objects still expose `x`, `y`, `width`, and `height` for compatibility with existing templates,
serializers, and renderers.

## Position

```python
from slim_report_core import Position

position = Position(50, 40)
```

`Position.x` and `Position.y` use the current page unit.

## Size

```python
from slim_report_core import Size

size = Size(300, 40)
```

`Size.width` and `Size.height` use the current page unit.

## Domain Objects

Report objects accept either raw coordinates or value objects:

```python
from slim_report_core import Object, Position, Size

box = Object(
    id="result_box",
    type="rectangle",
    position=Position(50, 150),
    size=Size(500, 100),
)
```

The object keeps legacy coordinate attributes synchronized:

```python
assert box.x == 50
assert box.y == 150
assert box.width == 500
assert box.height == 100
```

You can also assign value objects later:

```python
box.position = Position(60, 160)
box.size = Size(480, 90)
```

## Builder API

Builder object methods accept the same value objects:

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

Raw coordinates remain valid for short calls:

```python
report = ReportBuilder("Laboratory Report").text("Laboratory Report", x=50, y=40).build()
```

## Serialization Boundary

JSON output remains stable:

```json
{
  "id": "result_box",
  "type": "rectangle",
  "x": 50,
  "y": 150,
  "width": 500,
  "height": 100
}
```

Serializers may accept nested `position` and `size` input mappings, but they emit the existing
coordinate fields. This keeps the persistence format simple while letting Python code read more
clearly.
