# Changelog

All notable changes to Slim Report Designer will be documented in this file.

This project follows semantic versioning once public releases begin.

## [Unreleased]

### Changed

- Bumped package versions to the Sprint 6 development baseline `0.6.0a0`.
- Added `normalize_template` to the core public API and use it before JSON serializer validation.
- Added designer UI `get_designer_static_path()` resource helper.
- Added Flask production integration API with `TemplateProvider`, `FileSystemTemplateProvider`, custom URL prefixes, data providers, auth/permission hooks, and CSRF config injection.
- Moved reusable template storage providers into `slim_report_core.storage` with Flask compatibility re-exports.
- Added optional `SQLAlchemyTemplateProvider` for app-owned database template storage and sample data storage.
- Added SQLite database-backed Flask example and LIS template storage documentation.
- Expanded package/public API smoke tests and designer static package-data checks.
- Documented the multi-package editable install flow for Sprint 6.

### Fixed

- Template loading now tolerates missing serializer defaults such as `assets` and missing metadata title/name mirrors.

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
