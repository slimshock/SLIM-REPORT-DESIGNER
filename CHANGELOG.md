# Changelog

All notable changes to Slim Report Designer will be documented in this file.

This project follows semantic versioning once public releases begin.

## [Unreleased]

## [0.7.0] - 2026-07-15

### Added

- End-to-end MySQL report design with approved views and validated single-statement SELECT queries.
- Named runtime parameters, safe field discovery, dataset fields, canvas bindings, and New Report Wizard.
- Bounded unbuffered dataset execution and escaped, sandboxed live HTML preview with cancellation.
- Credential-reference persistence, offline-safe template reopen, freshness checks, and repair workflows.
- Self-contained Flask/MySQL demo, least-privilege SQL, release checks, wheel verification, and CI gates.

### Security

- Centralized Flask error mapping prevents raw exceptions, SQL, values, rows, and credentials from
  reaching clients.
- MySQL sessions require verified read-only mode and runtime execution remains bounded and streamed.
- Persisted reports reject plaintext or resolved credentials and omit runtime values and preview data.

### Changed

- Bumped package versions to the Sprint 6 development baseline `0.6.0a0`.
- Added `normalize_template` to the core public API and use it before JSON serializer validation.
- Added designer UI `get_designer_static_path()` resource helper.
- Added Flask production integration API with `TemplateProvider`, `FileSystemTemplateProvider`, custom URL prefixes, data providers, auth/permission hooks, and CSRF config injection.
- Moved reusable template storage providers into `slim_report_core.storage` with Flask compatibility re-exports.
- Added optional `SQLAlchemyTemplateProvider` for app-owned database template storage and sample data storage.
- Added dependency-free `DBAPITemplateProvider` and `PyMySQLTemplateProvider` for raw MySQL/PyMySQL template storage.
- Added SQLite database-backed Flask example and LIS template storage documentation.
- Added LIS integration hardening documentation for GitHub installs, PyMySQL storage, auth hooks, and patient portal safety.
- Added LIS hematology sample templates for filesystem/database/LIS preview testing.
- Added Sprint 6.4 asset provider interface, filesystem asset provider, asset ID validation, image `assetId` rendering, Flask asset routes, LIS asset docs, and a sample asset template.
- Added Sprint 6.5 advanced Table designer support with schema aliases, presets, richer column editing, grid controls, conditional formatting, section rows, two-column hematology sample data, and LIS table docs.
- Added Sprint 6.6 print/export workflow polish with Flask helper APIs, printable preview route, GET PDF export route, safe filenames, inline/download disposition, cleaner GET-route errors, permission coverage, LIS print docs, and compatibility for templates that store objects under `bands[].objects`.
- Expanded package/public API smoke tests and designer static package-data checks.
- Documented the multi-package editable install flow for Sprint 6.

### Fixed

- Template loading now tolerates missing serializer defaults such as `assets` and missing metadata title/name mirrors.
- Empty image values no longer render visible `Image` placeholder text in HTML preview or PDF export.

## 0.5.0-alpha - Sprint 5

### Added

- Framework-agnostic designer UI using plain HTML, CSS, and JavaScript modules.
- Flask designer integration for load, save, preview, PDF export, and JSON export workflows.
- Visual canvas, toolbox, object inspector, style controls, and page/band editing.
- Page Header, Detail, Page Footer, Group Header, and Group Footer band support.
- Repeating Detail rows with row-relative bindings.
- Basic Table object support in designer, HTML preview, and PDF export.
- Pagination for repeated Detail rows and Detail-band tables.
- Barcode and QR code objects.
- Aggregate/system variables including group/report aggregates and page/date fields.
- Computed fields with safe formulas.
- Conditional formatting with style overrides and hide actions.
- Print/export polish including page print settings, safe PDF filenames, and PDF metadata.
- Static designer server example.
- Flask sample templates covering fixed, repeating, table, grouped, aggregate, computed, conditional, barcode, and QR workflows.
- Docs, examples, and tests for Sprint 5 features.

### Known limitations

- Early alpha API and JSON template details may still change.
- Designer UI is not yet production packaged.
- Django and FastAPI adapters remain placeholders for future Sprint 6 work.
- Advanced pagination, subreports, nested groups, and advanced table designer features remain future work.
- Static browser mode requires a backend for HTML preview and PDF export.

### Added

- Initial monorepo foundation.
- Package skeletons for core, Flask, Django, FastAPI, and CLI distributions.
- Example application directories.
- Root documentation and contribution files.
- Import boundary test for the framework-agnostic core package.
- Framework-agnostic HTML and PDF rendering flow.
- Flask adapter preview, PDF export, provider registration, and designer save route.
- Pure Python rendering API and CLI rendering commands.
- Framework-agnostic designer UI package.
- Static designer server.
- Flask-hosted designer.
- Drag/drop canvas.
- Inspector.
- Style controls.
- Page properties.
- Image object support.
- Icons.
- Local browser version history.
- Zoom/grid/snap.
- Undo/redo.
- Multi-select, align, distribute, and layer controls.
- Lock/unlock.
- Report bands.
- Data Fields panel.
- Binding picker.
- Sample data editor.
- Placeholder/sample data toggle.
- Repeating Detail rows.
- Row-relative field bindings.
- Basic array-bound Table object with designer, HTML preview, and PDF export support.
- Basic multi-page pagination for repeating Detail rows and Detail-band tables.
- Barcode and QR code objects with designer, HTML preview, PDF export, and binding support.
- Preview/export debug headers for page, object, repeated-row, and table-row counts.
- `table_lab_result` Flask sample template.
- `barcode_qr_lab_result` Flask sample template.
- Improved preview/PDF fidelity.

### Changed

- README/docs updated for Sprint 5 designer progress.

### Known limitations

- Advanced table features such as nested tables, merged cells, and grouped tables are not implemented yet.
- Advanced pagination controls such as custom page breaks and widow/orphan rules are not implemented yet.
- Django/FastAPI adapters are placeholders/future work.
