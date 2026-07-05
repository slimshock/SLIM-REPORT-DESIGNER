# Architecture

Slim Report Designer is centered on the `Report` domain model.

## Current Boundaries

```text
Beginner Python API ----+
Builder API -----------+
Designer UI -----------+
Flask adapter ---------+       +--> HTML
CLI -------------------+-----> Report -----> Renderer
AI generated code -----+       +--> PDF
Serializer plugins ----+
```

`Report` is the center. It is the object that renderers, validators, adapters, designers, CLI
commands, and AI-generated code should manipulate.

Persistence formats sit at the edge:

```text
JSON file/dict ----> JSONSerializer -----+
YAML file/dict ----> YAMLSerializer -----+
XML plugin -------> XMLSerializer -------+----> Report
Database rows ----> Storage/Serializer --+
REST payload -----> RESTSerializer ------+

Report --------------------------------------> Serializer/Storage ---> external format
```

`Report` does not load, dump, save, or parse JSON. JSON is handled by serializers only. YAML,
database storage, REST payloads, binary packages, and XML plugins should follow the same contract.

```text
Framework boundary:

Flask route/request/response
    |
    v
slim_report_flask
    |
    +-- load/save through storage + serializer
    +-- resolve provider data
    v
Report
    |
    v
slim_report_core renderer
```

Drawable elements use one object hierarchy:

```text
Report
  Page
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

Page helpers instantiate these concrete classes and pass them through `page.add(...)`. Serializers
and JSON loading use `ObjectFactory` to create the same classes, so designers, adapters, AI tools,
CLI code, and direct Python code converge on the same domain model.

## Review Answers

- Can a beginner build a report without documentation? Mostly yes. The intended path is `Report("Title")`, `page = report.page()`, then `page.text(...)`, `page.field(...)`, `page.line(...)`, and `page.rectangle(...)`. The API now reads like normal Python object construction. Page and report collections support familiar operations such as iteration, `find()`, and validation.
- Can AI generate reports? Yes. AI can generate concise Python code using `Report`, page helpers, `Style`, `Position`, and `Size`; or generate JSON at the serializer boundary. The preferred AI target is `Report` or `ObjectFactory` because those APIs produce valid domain objects directly.
- Can the Designer manipulate `Report` directly? Architecturally yes. The current Flask designer edits JSON text, but the adapter deserializes to `Report` before saving or rendering. A richer designer should hydrate a `Report`, mutate pages and objects through `Page` and `ObjectFactory`, then serialize only when persisting.
- Can Flask use `Report` directly? Yes. `slim_report_flask` stores and loads templates through serializers, returns `Report` from storage, resolves provider data, and calls core renderers with `Report`.
- Can CLI use `Report` directly? Yes. The current CLI accepts JSON files, but its commands load them into `Report` before validate, inspect, or render. Future CLI commands can construct or mutate `Report` directly before saving through a serializer.
- Can JSON become optional? Yes. JSON is already optional after construction. It is the first built-in persistence format, not the domain model.
- Can YAML be added later? Yes. Add `YAMLSerializer(BaseSerializer)` that converts YAML mappings to and from `Report`; renderers and adapters should not change.
- Can XML become a plugin? Yes. XML should be implemented as a serializer plugin, likely outside the minimal core unless there is a strong reason to include it.
- Can database storage serialize `Report`? Yes. Database storage can either store serializer output as a document, decompose `Report` into relational rows, or use a custom serializer/storage pair. In all cases loading returns `Report`.

## Boundary Audit

- Does `Report` know JSON? No. JSON load/save/dump APIs live in `JSONSerializer`.
- Does Renderer know JSON? No. Renderers accept `Report` only.
- Can Builder API target `Report`? Yes. The builder constructs `Report`, `Page`, `Object`, and `Style` domain objects directly.
- Can developers use `Report` directly? Yes. `Report("Title").page().text(...)` is the primary API.
- Do adapters target `Report`? Yes. Flask and CLI load JSON at the boundary, then validate, inspect, or render `Report`.

## Layer Rules

- `slim_report_core.report` owns the `Report` aggregate.
- `slim_report_core.models` owns pages, styles, assets, and concrete `ReportObject` subclasses.
- `slim_report_core.object_factory` owns report object construction.
- `Report` is the primary public creation API.
- `slim_report_core.models.Position` and `Size` own object geometry readability while preserving the existing renderer coordinate fields.
- `slim_report_core.models.Style` owns style reuse and inheritance resolution.
- `slim_report_core.builder` owns fluent domain object construction.
- `slim_report_core.serialization` owns persistence formats.
- `slim_report_core.rendering` owns HTML/PDF render preparation and receives `Report`.
- Framework adapters own framework requests, responses, routing, and storage orchestration.
- Designer and AI layers should produce or mutate `Report`, not renderer-specific or JSON-specific structures.

## Target Flow

```text
Create/Load
  Report API -> Report
  Builder -> Report
  Designer -> Report
  JSONSerializer -> Report

Validate
  Report.validate()

Render
  Report -> render_html/render_pdf
  Object(Position/Size -> x/y/width/height) -> renderer
  Style -> resolved_values() -> renderer

Persist
  Report -> Serializer
```

## Lessons Learned

- The public API should start with `Report`, not a file format.
- JSON is useful because it is inspectable and designer-friendly, but it must remain replaceable.
- Object creation needs one policy point. `ObjectFactory` prevents page helpers, serializers, AI tools, and designers from inventing slightly different object shapes.
- Convenience APIs matter. `page.text("Hello")` is easier to generate, read, and test than a raw object dictionary.
- Validation should be structured and non-throwing for normal report quality issues. This supports designers, CLI output, and AI repair loops.
- Renderers should consume the domain model only. This keeps future storage formats and framework adapters from affecting rendering internals.
