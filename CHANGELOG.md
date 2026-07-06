# Changelog

All notable changes to Slim Report Designer will be documented in this file.

This project follows semantic versioning once public releases begin.

## [Unreleased]

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
- Preview/export debug headers for page, object, repeated-row, and table-row counts.
- `table_lab_result` Flask sample template.
- Improved preview/PDF fidelity.

### Changed

- README/docs updated for Sprint 5 designer progress.

### Known limitations

- Advanced table features such as nested tables, merged cells, formulas, and grouped tables are not implemented yet.
- Barcode/QR not implemented yet.
- Advanced pagination controls such as custom page breaks and widow/orphan rules are not implemented yet.
- Group headers/footers not implemented yet.
- Django/FastAPI adapters are placeholders/future work.
