# Documentation

Project documentation, architecture decisions, and design notes live here.

Start with:

- `principles.md`
- `manifesto.md`
- `architecture.md`
- `public-api.md`
- `domain-model.md`
- `object-model.md`
- `object-factory.md`
- `builder.md`
- `geometry.md`
- `styles.md`
- `serialization.md`
- `lessons-learned.md`
- `validation.md`
- `cloning.md`
- `querying.md`
- `events.md`
- `decisions/`

Current implementation notes:

- Rendering lives in `slim_report_core.rendering`.
- `Report` is the primary daily developer API.
- Drawable elements share one `ReportObject` inheritance model.
- `ObjectFactory` is the shared construction point for report objects.
- Serialization lives in `slim_report_core.serialization`.
- Domain validation lives on `Report.validate()`.
- Deep cloning lives on domain models through `clone()`.
- Object querying lives on `Report` and its callable `objects` collection.
- Framework-independent events are exposed through `Report.on()` and `Report.off()`.
- Builder classes create `Report` domain objects directly.
- `Position` and `Size` provide readable geometry value objects while preserving the existing coordinate fields.
- Reusable styles and style inheritance live in the `Style` domain object.
- Low-level renderers receive `Report` objects, not JSON mappings.
- Flask routes call core rendering functions and do not duplicate HTML or PDF rendering logic.
- Core import boundaries are enforced by tests.
- Sprint 4 architecture review is recorded in `decisions/0007-sprint-4-architecture-review.md`.
