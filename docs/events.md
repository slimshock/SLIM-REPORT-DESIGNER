# Event System

Slim Report Designer core includes a framework-independent observer system.

Events are synchronous and scoped to a `Report` instance. Framework adapters and plugins can subscribe without the core importing Flask, Django, FastAPI, or any other framework.

## Register Listeners

```python
from slim_report_core import ReportEvent
from slim_report_core.serialization import JSONSerializer

report = JSONSerializer().load("template.json")

def audit(event: ReportEvent) -> None:
    print(event.name, event.payload)

report.on("before_render", audit)
```

Remove a listener with `off()`:

```python
report.off("before_render", audit)
```

Listeners receive a `ReportEvent`:

```python
event.name      # "object_added"
event.source    # the Report instance
event.payload   # event-specific data
```

## Supported Events

- `before_render`
- `after_render`
- `before_export`
- `after_export`
- `object_added`
- `object_removed`
- `page_added`
- `page_removed`

## Payloads

Render events include:

```python
{
    "format": "html",
    "data": data,
}
```

`after_render` also includes `result`.

Export events include:

```python
{
    "exporter": "pdf",
    "data": data,
    "context": context,
}
```

`after_export` also includes `result`.

Mutation events include:

```python
{"object": report_object}
{"page": page}
```

## Extension Points

Common uses:

- audit report usage before or after rendering
- attach metrics around PDF exports
- synchronize designer state when objects or pages are added
- integrate storage or plugin behavior without coupling core to a framework

Events are not a validation mechanism. Validation should use `report.validate()`.
