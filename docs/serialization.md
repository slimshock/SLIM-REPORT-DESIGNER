# Serialization Architecture

Serialization is the boundary between persistence formats and the `Report` domain model.

The renderer does not know about JSON files, JSON dictionaries, Flask storage, databases, or HTTP APIs. It receives a `Report` instance.

## Core Contract

```text
persistence format -> serializer -> Report -> renderer
Report -> serializer -> persistence format
```

`Report` is the single source of truth once a template is loaded. Serializers convert external shapes into that model and convert the model back when saving.

## Built-In Serializer

`JSONSerializer` handles the current template format:

```python
from slim_report_core.serialization import JSONSerializer

serializer = JSONSerializer()

report = serializer.load("template.json")
report = serializer.loads(payload)
report = serializer.load_mapping(template_json)

template_json = serializer.dump_mapping(report)
payload = serializer.dumps(report)
serializer.save(report, "template.json")
```

`Report` intentionally has no JSON load/save helpers. Serialization belongs here, not on the domain model.

## Current Template Shape

The current JSON template shape includes `version`, `metadata`, `page`, `bands`, `objects`, `assets`, and optional `data`.

`data.sample` can store sample render data for preview/export. `data.fields` can store field metadata for the designer's Data Fields panel and binding picker. See `json-template-schema.md` and `data-fields.md` for the practical early-alpha schema notes.

## Future Serializers

Future formats should implement `BaseSerializer` without changing renderers:

- YAML
- Database records
- REST resources
- Binary packages
- XML plugin formats

Each serializer should own format-specific validation, loading, and saving. It should return `Report` objects to the rest of the core.

JSON can become optional for applications that create reports directly with Python, load reports
from a database, or install another serializer. The required boundary is `Report`, not JSON.

## Storage Boundary

Storage may call a serializer, but storage is not the domain model:

```text
Storage backend -> serializer/rehydrator -> Report
Report ---------> serializer/decomposer -> Storage backend
```

Database storage can store `Report` as a JSON document, YAML document, relational rows, or a custom
record shape. The adapter-facing load method should still return `Report`.

## Rendering Boundary

Renderers in `slim_report_core.rendering` expect `Report` only.

The top-level rendering API follows the same rule:

```python
from slim_report_core import render_html, render_pdf
from slim_report_core.serialization import JSONSerializer

report = JSONSerializer().load("template.json")
html = render_html(report, data)
pdf = render_pdf(report, data)
```

Do not pass JSON dictionaries to renderers. Deserialize them into `Report` first.
