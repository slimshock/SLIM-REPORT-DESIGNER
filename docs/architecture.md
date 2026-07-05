# Architecture

Slim Report Designer is centered on the `Report` domain model. A report may be created by Python
code, a builder, a designer, AI-generated code, a framework adapter, the CLI, or a serializer, but
all of those paths converge on the same `Report` aggregate before validation, rendering, or
persistence.

## System Diagram

```text
                           +------------------+
Beginner Python API ------>|                  |
Builder API -------------->|                  |
AI generated code -------->|                  |       +----------------+
Designer ----------------->|      Report      |------>| HTML renderer  |
Flask adapter ------------>|  domain model    |       +----------------+
CLI ---------------------->|                  |       +----------------+
Serializer plugins ------->|                  |------>| PDF renderer   |
                           +------------------+       +----------------+
                                  |
                                  v
                           Report.validate()
```

`Report` is the center. Renderers, validators, adapters, designers, CLI commands, and AI-generated
code should manipulate domain objects instead of treating JSON or renderer structures as the source
of truth.

## Persistence Boundary

Persistence formats sit at the edge:

```text
JSON file/dict ----> JSONSerializer --------+
YAML file/dict ----> YAMLSerializer --------+
XML plugin -------> XMLSerializer plugin ---+----> Report
Database rows ----> Storage/Serializer -----+
REST payload -----> RESTSerializer ---------+
Binary package ---> PackageSerializer ------+

Report ------------------------------------------> Serializer/Storage ---> external format
```

`Report` does not load, dump, save, or parse JSON. JSON is handled by serializers only. YAML,
database storage, REST payloads, binary packages, and XML plugins should follow the same contract.

## Framework Boundary

```text
Flask route/request/response
    |
    v
slim_report_flask
    |
    +-- load/save through storage and serializer
    +-- resolve provider data
    v
Report
    |
    +-- validate with Report.validate()
    +-- render through slim_report_core
    v
HTML/PDF response
```

Framework adapters own routes, requests, responses, provider registration, and storage
orchestration. They do not duplicate core rendering logic.

## Designer Boundary

```text
Designer state
    |
    v
Report + Page + ReportObject
    |
    +-- ObjectFactory for object creation
    +-- Report.validate() for repair feedback
    v
Serializer only when saving
```

The current Flask designer edits JSON text as an interim interface. The target designer hydrates a
`Report`, mutates pages and objects through the domain API, and serializes only at the persistence
boundary.

## Object Model

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

Page helpers instantiate concrete classes and pass them through `page.add(...)`. Serializers and
JSON loading use `ObjectFactory` to create the same classes, so designers, adapters, AI tools, CLI
code, and direct Python code converge on the same domain model.

## Sprint 4 Review Answers

- Can a beginner build a report without documentation? Mostly yes. The intended path is `Report("Title")`, `page = report.page()`, then `page.text(...)`, `page.field(...)`, `page.line(...)`, and `page.rectangle(...)`. The API reads like normal Python object construction, and report/page collections support familiar operations such as iteration, `find()`, and validation.
- Can AI generate reports? Yes. AI can generate concise Python code using `Report`, page helpers, `Style`, `Position`, and `Size`; or it can generate serializer input at the persistence boundary. The preferred AI target is the public `Report` API because the same code can be validated, rendered, cloned, and serialized.
- Can the Designer manipulate `Report` directly? Yes. The target designer should mutate `Report`, `Page`, and concrete `ReportObject` instances directly, using `ObjectFactory` for new objects. JSON remains an interim editor and save format, not the designer model.
- Can Flask use `Report` directly? Yes. `slim_report_flask` storage loads templates into `Report`, provider callbacks supply data, and routes call core renderers with `Report`.
- Can CLI use `Report` directly? Yes. The current CLI accepts JSON files, but each command deserializes into `Report` before validation, inspection, or rendering. Future commands can construct or mutate `Report` before saving through a serializer.
- Can JSON become optional? Yes. JSON is already optional after a `Report` exists. Applications can create reports directly in Python or load them through another storage/serializer pair.
- Can YAML be added later? Yes. Add `YAMLSerializer(BaseSerializer)` that converts YAML mappings to and from `Report`; renderers, validators, and framework adapters should not change.
- Can XML become a plugin? Yes. XML should be a serializer plugin unless there is a strong reason to make it built in.
- Can database storage serialize `Report`? Yes. Database storage can store serializer output as a document, decompose `Report` into relational rows, or use a custom serializer/storage pair. Loading must return `Report`.

## Boundary Audit

- `Report` does not expose JSON load/save/dump APIs.
- Renderers accept `Report`, not JSON dictionaries or file paths.
- Builder code creates `Report`, `Page`, `Object`, and `Style` domain objects directly.
- Flask and CLI load JSON at the boundary, then operate on `Report`.
- Designer and AI integrations should produce or mutate `Report`, not renderer-specific or JSON-specific structures.
- Storage providers may choose any internal format, but public load operations should return `Report`.

## Layer Rules

- `slim_report_core.report` owns the `Report` aggregate.
- `slim_report_core.models` owns pages, styles, assets, and concrete `ReportObject` subclasses.
- `slim_report_core.object_factory` owns report object construction policy.
- `Report` is the primary public creation API.
- `Position` and `Size` make geometry readable while preserving renderer coordinate fields.
- `Style` owns style reuse and inheritance resolution.
- `slim_report_core.builder` owns optional fluent domain object construction.
- `slim_report_core.serialization` owns persistence formats.
- `slim_report_core.rendering` owns HTML/PDF render preparation and receives `Report`.
- Framework adapters own framework requests, responses, routing, and storage orchestration.

## Target Flow

```text
Create/load:
  Report API        -> Report
  Builder           -> Report
  Designer          -> Report
  JSONSerializer    -> Report
  Future serializers -> Report

Validate:
  Report.validate()

Render:
  Report -> render_html/render_pdf
  Object(Position/Size -> x/y/width/height) -> renderer
  Style -> resolved_values() -> renderer

Persist:
  Report -> Serializer/Storage
```

## Lessons

- The public API should start with `Report`, not a file format.
- JSON is useful because it is inspectable and designer-friendly, but it must remain replaceable.
- Object creation needs one policy point. `ObjectFactory` prevents page helpers, serializers, AI tools, and designers from inventing slightly different object shapes.
- Convenience APIs matter. `page.text("Hello")` is easier to generate, read, and test than a raw object dictionary.
- Validation should be structured and non-throwing for normal report quality issues. This supports designers, CLI output, and AI repair loops.
- Renderers should consume the domain model only. This keeps future storage formats and framework adapters from affecting rendering internals.
