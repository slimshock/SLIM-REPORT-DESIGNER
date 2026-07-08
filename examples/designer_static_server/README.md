# Designer Static Server

This example serves the framework-agnostic designer UI without Flask, Django, FastAPI, or any backend adapter.

## Run

From the repository root:

```bash
python examples/designer_static_server/serve.py
```

Open:

```text
http://127.0.0.1:8008/
```

## What Works In Static Mode

- Visual designer canvas
- Toolbox and object inspector
- Data Fields panel and binding picker
- JSON import/export
- Local browser version history
- Editing `data.sample`
- Editing/preserving `data.fields`
- Placeholder/sample data canvas toggle
- Zoom, grid, snap, undo/redo, multi-select, and locking
- Page, band, formula, conditional formatting, and print setting edits

## What Requires A Backend

- HTML preview through `slim_report_core`
- PDF export
- Server-side template storage
- Provider-backed render data

Use the Flask example when you need preview/export integration.
