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
Human Python code ----+
AI generated code ----+
Designer ------------+
Flask adapter --------+----> Report ----> Renderer
CLI -----------------+
Serializers ---------+
```

Persistence remains replaceable:

```text
JSON ----+
YAML ----+
XML -----+----> Serializer/Storage ----> Report
DB ------+
REST ----+
```

## Review Answers

- Beginners can build a report through `Report`, `page()`, and page helper methods.
- AI can generate reports by targeting the same public API or by generating serializer input.
- The Designer can manipulate `Report` directly; the current JSON editor is only an interim UI.
- Flask can use `Report` directly after storage/serializer loading.
- CLI can use `Report` directly after loading input files.
- JSON can become optional because `Report` and renderers do not depend on JSON.
- YAML can be added as another `BaseSerializer`.
- XML can be added as a serializer plugin.
- Database storage can serialize or decompose `Report`, but loading must return `Report`.

## Consequences

Sprint 5 should focus on persistence without moving storage concerns into `Report`.

Sprint 6 should build the canvas/designer against `Report`, `Page`, `ReportObject`, and
`ObjectFactory` instead of editing renderer-specific or JSON-specific structures directly.

Future plugin work should treat serializers and storage providers as first-class extension points.
