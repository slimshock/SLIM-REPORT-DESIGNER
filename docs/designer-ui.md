# Designer UI

The Designer UI is the framework-agnostic visual editor for Slim Report Designer templates.

It is an early-alpha editor for building and editing JSON report templates with a visual canvas. It is useful today for lab-style reports, fixed layouts, fields, bands, images, barcode/QR labels, basic tables, and repeating Detail rows.

## Purpose

The designer lets users edit reports without writing Python. It produces the same JSON template shape that `slim_report_core.serialization.JSONSerializer` can load into a `Report`.

## Architecture

The UI package is `slim_report_designer_ui`. It ships static files:

- HTML
- CSS
- JavaScript
- icons

There is no React, no Vue, no npm build step, and no frontend framework dependency.

Framework adapters such as Flask host the same static files and provide API routes for loading, saving, previewing, and exporting templates.

## Run Static Mode

```bash
python examples/designer_static_server/serve.py
```

Open:

```text
http://127.0.0.1:8008/
```

Static mode works without Flask. JSON import/export and local version history work in the browser. PDF export requires a backend API.

## Run Inside Flask

```bash
python examples/flask_app/app.py
```

Open:

```text
http://127.0.0.1:5000/report-designer/designer?template=lab_result
http://127.0.0.1:5000/report-designer/designer?template=cerebro_cbc
http://127.0.0.1:5000/report-designer/designer?template=repeating_lab_result
http://127.0.0.1:5000/report-designer/designer?template=table_lab_result
http://127.0.0.1:5000/report-designer/designer?template=barcode_qr_lab_result
```

## Supported Tools

- Text
- Field
- Line
- Rectangle
- Image
- Barcode
- QR Code
- Table

## Supported Canvas Features

- Drag/drop
- Resize
- Style inspector
- Page properties
- Image object support
- Zoom/grid/snap
- Undo/redo
- Multi-select
- Align/distribute/layers
- Lock/unlock
- Bands
- Data Fields panel
- Binding picker
- Sample data editor
- Placeholder/sample display toggle
- Repeating Detail rows
- Basic array-bound tables
- Barcode and QR code objects
- Basic preview/export pagination for repeating Detail rows and Detail-band tables

## Local Version History

The designer stores local browser history so users can recover recent work while editing. This is separate from application persistence. In Flask mode, saving still goes through the Flask adapter API.

## JSON Import/Export

The designer can import and export JSON templates. This is the easiest way to move templates between static mode, Flask mode, tests, and examples while the project is early alpha.

## Static Mode vs Flask Mode

Static mode:

- runs from `examples/designer_static_server/serve.py`
- works without a framework adapter
- supports browser-local editing and JSON import/export
- cannot export PDF unless connected to a backend API

Flask mode:

- hosts the same designer UI at `/report-designer/designer`
- loads and saves templates through Flask routes
- previews HTML through `slim_report_core`
- exports PDF through `slim_report_core`
- can use provider data and `template.data.sample`

## Known Limitations

- Advanced table features such as nested tables, merged cells, formulas, grouped tables, and complex pagination are not implemented yet.
- Custom page breaks, group pagination, and widow/orphan rules are not implemented yet.
- Group headers/footers are not implemented yet.
- Barcode/QR objects render without additional frontend dependencies. Current built-in output uses deterministic fallback visuals rather than a full barcode/QR encoder for every symbology.
- Django and FastAPI adapters are future work.
