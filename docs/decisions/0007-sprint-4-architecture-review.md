# ADR-0007: Sprint 4 Architecture Review

**Status:** Accepted

**Date:** 2026-07-05

## Context

Sprint 4 finished the developer-facing `Report` API, concrete report object model, reusable styles,
page collection behavior, `ObjectFactory`, serializer boundaries, and developer API tests.

The project needed a final architecture review before moving into persistence and canvas work.

## Decision

Slim Report Designer is `Report` first.

The beginner API is:

```python
from slim_report_core import Report

report = Report("Demo")
page = report.page()
page.text("Hello")
page.field("patient.name")
```

All first-party and future integrations should converge on this model:

```text
                           +------------------+
Human Python code -------->|                  |
AI generated code -------->|                  |
Designer ----------------->|      Report      |----> Renderer
Flask adapter ------------>|  domain model    |----> Validator
CLI ---------------------->|                  |----> Serializer/Storage
Serializers -------------->|                  |
                           +------------------+
```

Persistence remains replaceable:

```text
JSON file/dict ----> JSONSerializer --------+
YAML file/dict ----> YAMLSerializer --------+
XML plugin -------> XMLSerializer plugin ---+----> Report
Database rows ----> Storage/Serializer -----+
REST payload -----> RESTSerializer ---------+
Binary package ---> PackageSerializer ------+

Report ------------------------------------------> Serializer/Storage ---> external format
```

## Review Answers

- Beginners can build a report through `Report`, `page()`, and page helper methods without first learning the JSON format.
- AI can generate reports by targeting the same public API or by generating serializer input at the persistence boundary. The preferred target is the public `Report` API because it produces domain objects directly.
- The Designer can manipulate `Report` directly; the current JSON editor is only an interim UI. The target designer should use `Report`, `Page`, concrete `ReportObject` classes, and `ObjectFactory`.
- Flask can use `Report` directly after storage/serializer loading.
- CLI can use `Report` directly after loading input files.
- JSON can become optional because `Report`, validation, and renderers do not depend on JSON.
- YAML can be added as another `BaseSerializer`.
- XML can be added as a serializer plugin.
- Database storage can serialize or decompose `Report`, but loading must return `Report`.

## Direct Use Matrix

```text
Layer/API        May construct Report   May mutate Report   Owns persistence format
Beginner API     yes                    yes                 no
AI code          yes                    yes                 no
Designer         yes                    yes                 no
Flask adapter    yes                    yes                 no
CLI              yes                    yes                 no
Serializer       yes                    yes                 yes
Storage          yes                    yes                 yes
Renderer         no                     no                  no
```

Renderers are intentionally read-only consumers of `Report`.

## Consequences

Sprint 5 should focus on persistence without moving storage concerns into `Report`.

Sprint 6 should build the canvas/designer against `Report`, `Page`, `ReportObject`, and
`ObjectFactory` instead of editing renderer-specific or JSON-specific structures directly.

Future plugin work should treat serializers and storage providers as first-class extension points.

README examples and docs should lead with direct `Report` usage, then show JSON only as an explicit
serialization choice.
