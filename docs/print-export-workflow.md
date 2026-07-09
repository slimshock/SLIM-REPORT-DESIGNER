# Print/Export Workflow

Sprint 6.6 adds app-facing helpers and GET routes for previewing and exporting saved templates from Flask application pages.

## Flask Helpers

`SlimReportDesigner` exposes helper methods for app routes:

```python
html = designer.render_template_html(
    "lab_result",
    request_args={"order_id": "43"},
)

pdf_bytes = designer.render_template_pdf(
    "lab_result",
    request_args={"order_id": "43"},
)
```

Helpers load the template, resolve data, pass the configured asset provider, and call the core HTML/PDF renderers.

Data is resolved in this order:

1. Explicit `data` passed to the helper or API body
2. `data_provider(template_id, request_args, request_json)`
3. Named registered provider on the template
4. Template provider sample data
5. `template.data.sample`
6. Empty dict

## Existing POST APIs

The designer still uses:

- `POST /report-designer/api/preview`
- `POST /report-designer/api/export/pdf`

These remain compatible with posted template JSON and optional `data`.

## Template Compatibility

Print and export use the core template normalizer before rendering. Both common
JSON shapes are accepted:

- Flat templates with top-level `objects`
- Band-based templates with objects nested under `bands[].objects`

When top-level `objects` is present and non-empty, it is preserved and nested
band objects are not duplicated. When top-level `objects` is missing or empty,
objects are flattened from `bands[].objects` internally and assigned to the
owning band ID for rendering. Band metadata remains available to the renderer.

## Printable Preview

Saved templates can be opened as printable HTML:

```text
GET /report-designer/print/<template_id>?order_id=43
```

Add `auto_print=1` to call `window.print()` after load:

```text
GET /report-designer/print/lab_result?order_id=43&auto_print=1
```

The route hides preview controls, uses a white print background, and keeps existing report pagination.

## GET PDF Export

Saved templates can be exported without a POST body:

```text
GET /report-designer/export/pdf/<template_id>?order_id=43
```

By default the response is inline:

```text
Content-Disposition: inline; filename="report-lab-result.pdf"
```

Use `download=1` for attachment:

```text
GET /report-designer/export/pdf/lab_result?order_id=43&download=1
```

## Filenames

Filename priority:

1. Query param `filename`
2. `filename_provider(template_id, data, request_args)`
3. Template print settings/default filename
4. `report-{template_id}.pdf`

All filenames are sanitized, slashes are removed, path traversal is blocked, Windows-reserved names fall back safely, and `.pdf` is enforced.

```python
def filename_provider(template_id, data, request_args):
    return f"lab-result-{request_args.get('order_id')}.pdf"

designer = SlimReportDesigner(
    template_provider=provider,
    data_provider=data_provider,
    filename_provider=filename_provider,
)
```

## Permissions

Configured hooks are applied consistently:

- Designer page: authentication and template view permission
- Template list/get: view permission
- Printable preview: view permission
- POST preview: view permission
- PDF export: export permission
- Template save: edit permission
- Asset routes: asset hooks when configured

## Errors

API routes return JSON errors. Printable/PDF GET routes return JSON when requested with `Accept: application/json`; otherwise they return a simple readable HTML error page. Server-side exceptions are logged and stack traces are not sent to clients.

## Limitations

The GET routes render saved templates by ID. Use the existing POST APIs for unsaved designer-state previews. Django and FastAPI adapters remain future work.
