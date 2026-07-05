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

The beginner API does not need to expose the storage format first. The first useful lesson for a new
developer is "make a report, add a page object, render it." JSON, YAML, XML, and database storage can
wait until the developer needs persistence.

## Direct Manipulation Beats Format Editing

The Designer, Flask adapter, CLI, and AI integrations can all manipulate `Report` directly.

```text
External input -> serializer/storage -> Report -> validate/render/mutate -> serializer/storage
```

The current JSON designer is acceptable as a temporary tool, but the long-term designer should not
make JSON dictionaries its internal model. It should hydrate `Report`, mutate `Page` and
`ReportObject` instances, use `ObjectFactory` for creation, and serialize only when saving.

## JSON Is Useful, Not Central

JSON is valuable for examples, storage, browser editing, and AI generation, but it is no longer the
center of the system. It is one serializer.

This means:

- Renderers do not know JSON exists.
- `Report` does not expose JSON load/save helpers.
- YAML can be added without renderer changes.
- XML can live as a plugin serializer.
- Database storage can load and save `Report` without pretending the database shape is the domain.

JSON can become optional because the runtime boundary is `Report`, not a file extension. A database
adapter may store JSON in one column, relational rows across many tables, or a custom binary payload;
all are valid if loading returns `Report`.

## AI Should Generate the Public API

AI output is most useful when it targets the same public API a human would write:

```python
from slim_report_core import Report

report = Report("Laboratory Result")
page = report.page()
page.text("LABORATORY RESULT", x=50, y=40)
page.field("patient.name", x=50, y=90)
```

Generated JSON is still allowed at the serializer boundary, but generated Python has better
discoverability, easier validation, and fewer chances to encode storage-specific assumptions.

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
