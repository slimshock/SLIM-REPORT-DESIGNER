# Documentation

Project documentation, architecture decisions, and design notes live here.

Start with:

- [Architecture](architecture.md)
- [Public API](public-api.md)
- [Designer UI](designer-ui.md)
- [Flask integration](flask-integration.md)
- [Flask production integration](flask-production-integration.md)
- [Template storage](template-storage.md)
- [LIS Flask template storage](lis-flask-template-storage.md)
- [LIS integration hardening](lis-integration-hardening.md)
- [Asset Manager](asset-manager.md)
- [LIS Asset Management](lis-asset-management.md)
- [Advanced Table Designer](advanced-table-designer.md)
- [LIS Table Layouts](lis-table-layouts.md)
- [Print/Export Workflow](print-export-workflow.md)
- [LIS Print Workflow](lis-print-workflow.md)
- [JSON template schema](json-template-schema.md)
- [Data Sources](data-sources.md)
- [SQL Validation](sql-validation.md)
- [MySQL Data-Source Provider](mysql-data-source-provider.md)
- [Data Fields](data-fields.md)
- [Repeating Detail rows](repeating-detail-rows.md)
- [Grouping](grouping.md)
- [Aggregate and system fields](aggregate-and-system-fields.md)
- [Formulas](formulas.md)
- [Conditional formatting](conditional-formatting.md)
- [Sprint 5 release notes](release-notes-sprint-5.md)
- [Sprint 5 merge checklist](merge-checklist-sprint-5.md)
- [Roadmap](roadmap.md)
- [Domain model](domain-model.md)
- [Object model](object-model.md)
- [Object factory](object-factory.md)
- [Builder](builder.md)
- [Geometry](geometry.md)
- [Styles](styles.md)
- [Serialization](serialization.md)
- [Validation](validation.md)
- [Cloning](cloning.md)
- [Querying](querying.md)
- [Events](events.md)
- [Principles](principles.md)
- [Manifesto](manifesto.md)
- [Lessons learned](lessons-learned.md)
- [Architecture decisions](decisions/)

Current implementation notes:

- Rendering lives in `slim_report_core.rendering`.
- `Report` is the primary daily developer API.
- Beginners, AI tools, designers, Flask, and CLI should all target `Report` directly.
- The Canvas designer UI lives in `slim_report_designer_ui` as static HTML/CSS/JavaScript.
- Framework adapters host the Canvas UI and provide load/save/preview/export APIs.
- Drawable elements share one `ReportObject` inheritance model.
- `ObjectFactory` is the shared construction point for report objects.
- Serialization lives in `slim_report_core.serialization`.
- Template storage providers live in `slim_report_core.storage`.
- Data-source and dataset metadata live in `slim_report_core.data_sources`.
- JSON is the first built-in serializer, not a required runtime model.
- Domain validation lives on `Report.validate()`.
- Low-level renderers receive `Report` objects, not JSON mappings.
- Flask routes call core rendering functions and do not duplicate HTML or PDF rendering logic.
- Core import boundaries are enforced by tests.
