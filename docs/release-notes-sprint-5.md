# Sprint 5 Release Notes

Sprint 5 prepares Slim Report Designer as an early alpha / pre-release report designer and rendering toolkit.

## What Changed

- Added the framework-agnostic static designer UI with plain HTML, CSS, and JavaScript modules.
- Added Flask integration for designer hosting, template APIs, HTML preview, PDF export, and JSON export.
- Added a visual canvas, toolbox, object inspector, page properties, band editing, zoom, grid, snap, undo/redo, multi-select, locking, alignment, distribution, and layer controls.
- Added Page Header, Detail, Page Footer, Group Header, and Group Footer support.
- Added repeating Detail rows, basic Table objects, pagination, barcode objects, and QR code objects.
- Added aggregate/system variables, computed fields with safe formulas, conditional formatting, and print/export settings.
- Added sample templates, documentation, and tests for the Sprint 5 feature set.

## Run The Flask Example

```bash
python examples/flask_app/app.py
```

Open:

```text
http://127.0.0.1:5000/report-designer/designer
```

Sample templates can be opened with `?template=<template_id>`, for example:

```text
http://127.0.0.1:5000/report-designer/designer?template=aggregate_grouped_lab_result
```

## Run The Static Designer

```bash
python examples/designer_static_server/serve.py
```

Open:

```text
http://127.0.0.1:8008/
```

Static mode supports canvas editing, JSON import/export, local browser history, and sample/field metadata editing. HTML preview and PDF export require a backend such as the Flask example.

## Main Supported Features

- Text, Field, Line, Rectangle, Image, Table, Barcode, and QR Code objects.
- Page Header, Detail, Page Footer, Group Header, and Group Footer bands.
- Repeating Detail rows, basic table pagination, group/report aggregates, system variables, safe formulas, conditional formatting, and print/export settings.
- JSON template serialization, HTML preview, PDF export, Flask routes, and static designer hosting.

## Known Limitations

- Early alpha; API and template schema may still change.
- Designer UI is not yet production packaged.
- Django/FastAPI adapters are not yet implemented.
- Advanced pagination, subreports, nested groups, and advanced table designer features are not yet complete.
- Browser/static mode needs a backend for HTML preview and PDF export.

## Recommended Sprint 6 Next Steps

- Package and document the designer UI for broader distribution.
- Add Django and FastAPI adapters.
- Expand advanced pagination and group pagination controls.
- Continue hardening table designer workflows.
- Define longer-term subreport and asset-management design.
