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
- Improved preview/PDF fidelity.

### Changed

- README/docs updated for Sprint 5 designer progress.

### Known limitations

- Full table component not implemented yet.
- Barcode/QR not implemented yet.
- Full pagination/multi-page repeat overflow not implemented yet.
- Group headers/footers not implemented yet.
- Django/FastAPI adapters are placeholders/future work.
