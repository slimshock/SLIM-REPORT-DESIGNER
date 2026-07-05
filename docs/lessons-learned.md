# Lessons Learned

Sprint 4 clarified the shape of Slim Report Designer.

## Report First

`Report` is the framework. A beginner should be able to write:

```python
from slim_report_core import Report

report = Report("Demo")
page = report.page()

page.text("Hello")
page.field("patient.name")
```

That path is now the architectural baseline. Builders, serializers, designers, CLI commands,
framework adapters, and AI integrations should converge on the same `Report` object model.

## JSON Is Useful, Not Central

JSON is valuable for examples, storage, browser editing, and AI generation, but it is no longer the
center of the system. It is one serializer.

This means:

- Renderers do not know JSON exists.
- `Report` does not expose JSON load/save helpers.
- YAML can be added without renderer changes.
- XML can live as a plugin serializer.
- Database storage can load and save `Report` without pretending the database shape is the domain.

## Factories Prevent Drift

`ObjectFactory` exists because object construction happens from several places:

- Python page helpers
- JSON deserialization
- future designers
- AI generated reports
- future storage and serializer plugins

One factory prevents each layer from inventing a slightly different text, field, line, or rectangle
shape.

## Convenience Is Architecture

APIs such as `page.text("Hello")`, `page.find("title")`, and `report.validate()` are not just
syntax. They define how people, designers, and AI systems will naturally create and repair reports.

When the simple path is also the correct path, the architecture becomes easier to preserve.

## Validation Is a Repair Interface

Validation returns structured errors instead of raising for normal report issues. That helps:

- CLI users see actionable messages.
- Designers highlight broken fields.
- AI tools repair invalid reports.
- Framework adapters return useful responses.

## Boundaries Stay Small

Framework adapters should handle framework work. Storage should handle persistence. Serializers
should handle external formats. Renderers should render `Report`.

Keeping those boundaries small is what allows Flask, CLI, Designer, AI, YAML, XML, and database
storage to share one core.
