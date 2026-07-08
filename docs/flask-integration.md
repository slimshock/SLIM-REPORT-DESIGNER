# Flask Integration

The Flask adapter hosts the framework-agnostic designer UI and exposes API routes for template loading, saving, preview, and PDF export.

Important architecture rule: Flask does not own rendering. It calls `slim_report_core`.

## Run The Example

```bash
python examples/flask_app/app.py
```

Open:

```text
http://127.0.0.1:5000/report-designer/designer?template=lab_result
http://127.0.0.1:5000/report-designer/designer?template=cerebro_cbc
http://127.0.0.1:5000/report-designer/designer?template=repeating_lab_result
http://127.0.0.1:5000/report-designer/designer?template=table_lab_result
http://127.0.0.1:5000/report-designer/designer?template=grouped_lab_result
http://127.0.0.1:5000/report-designer/designer?template=aggregate_grouped_lab_result
http://127.0.0.1:5000/report-designer/designer?template=complete_sprint5_lab_report
http://127.0.0.1:5000/report-designer/designer?template=computed_fields_lab_result
http://127.0.0.1:5000/report-designer/designer?template=conditional_lab_result
http://127.0.0.1:5000/report-designer/designer?template=barcode_qr_lab_result
```

## Designer Route

```text
GET /report-designer/designer
```

The route serves the static designer UI from `slim_report_designer_ui` and injects the Flask API base path.

## API Routes

```text
GET  /report-designer/api/templates/<id>
POST /report-designer/api/templates/<id>
POST /report-designer/api/preview
POST /report-designer/api/export/pdf
```

The designer uses these routes to load, save, preview, and export templates.

Legacy/example routes also exist for direct preview/export:

```text
GET /report-designer/templates/<template_id>/preview/<record_id>
GET /report-designer/templates/<template_id>/export/pdf/<record_id>
```

## Sample Templates

The example app loads JSON templates from:

```text
examples/flask_app/sample_templates/
```

Included examples:

- `lab_result`
- `cerebro_cbc`
- `repeating_lab_result`
- `table_lab_result`
- `grouped_lab_result`
- `aggregate_grouped_lab_result`
- `complete_sprint5_lab_report`
- `computed_fields_lab_result`
- `conditional_lab_result`
- `barcode_qr_lab_result`

## Provider Data

Providers are registered in `examples/flask_app/app.py` with `@designer.provider("<template_id>")`.

When previewing or exporting a stored template route, the adapter resolves provider data and passes it to core rendering:

```text
Flask route -> provider data -> Report -> render_html/render_pdf -> response
```

## `template.data.sample`

Designer API preview/export can use `template.data.sample` when explicit render data is not supplied. This lets templates carry beginner-friendly sample data for local previewing.

## `template.data.fields`

`template.data.fields` is preserved when templates are loaded and saved. It describes field metadata for the Data Fields panel, binding picker, and sample data workflows.

## Repeating Detail Rows

Repeating Detail rows use array data. A Detail band can enable repeat settings with a `data_path`, such as:

```json
{
  "repeat": {
    "enabled": true,
    "data_path": "results",
    "row_height": 24,
    "preview_rows": 20,
    "empty_message": "No records"
  }
}
```

Field objects inside the repeating Detail band can use row-relative bindings. For a row in `results`, `test` resolves against the current row. `results[].test` also resolves against the current row when the band repeats over `results`.

## Preview And Export Responses

Preview returns `text/html`. PDF export returns `application/pdf` with a safe `Content-Disposition` filename. Preview/export failures return JSON with a clear `error` message and a status code appropriate to the failure.

The response includes lightweight debug headers such as page count, object count, template name, and renderer name to make integration smoke checks easier.

## Rendering Boundary

Templates are deserialized into `Report` before rendering:

```python
report = template_store.load_report("lab_result")
html = report.render_html(data)
pdf_bytes = report.render_pdf(data)
```

The Flask adapter owns requests and responses. `slim_report_core` owns the renderers.
