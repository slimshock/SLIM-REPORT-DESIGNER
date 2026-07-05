# ADR-0005: Report Domain Boundary

**Status:** Accepted

**Date:** 2026-07-05

## Context

Early foundation work used JSON templates directly in several places because JSON was the first persistence format.

As the core evolved, `Report` became the domain model. Keeping JSON load/save helpers on `Report` would make JSON appear to be the domain source of truth and would make future YAML, database, REST, binary, Builder, Designer, and AI integrations harder to keep clean.

## Decision

`Report` is the framework-agnostic domain model and must not expose JSON-specific persistence methods.

JSON conversion belongs to `slim_report_core.serialization.JSONSerializer`.

Renderers receive `Report` only. Adapters and tools may load JSON, but they must deserialize it into `Report` before validation or rendering.

## Consequences

Callers should use:

```python
from slim_report_core.serialization import JSONSerializer

serializer = JSONSerializer()
report = serializer.load("template.json")
serializer.save(report, "template.json")
```

They should not use `Report.load_json()`, `Report.load_from_dict()`, `report.to_dict()`, `report.to_json()`, or `report.save_json()`.

Future Builder, Designer, Flask, CLI, AI, YAML, XML, and database integrations should target
`Report` directly. Persistence formats and storage mechanisms remain replaceable boundary layers.

The direct manipulation rule is intentional:

```text
Designer/AI/Flask/CLI -> Report -> validate/render/serialize
```

These integrations may load or save through a serializer, but their in-memory working model should
be `Report`, not JSON dictionaries or renderer-specific structures.
