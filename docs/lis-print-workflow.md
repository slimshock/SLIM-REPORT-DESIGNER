# LIS Print Workflow

Slim Report Designer does not hardcode LIS tables, SQL, patients, or order models. The host LIS should provide data through `data_provider` and link to saved templates by ID.

## Button Examples

Printable preview:

```html
<a href="/report-designer/print/lab_result?order_id=43" target="_blank">
  Print Preview
</a>
```

Auto-open browser print:

```html
<a href="/report-designer/print/lab_result?order_id=43&auto_print=1" target="_blank">
  Print
</a>
```

Inline PDF:

```html
<a href="/report-designer/export/pdf/lab_result?order_id=43" target="_blank">
  Export PDF
</a>
```

Download PDF:

```html
<a href="/report-designer/export/pdf/lab_result?order_id=43&download=1">
  Download PDF
</a>
```

Template designer:

```html
<a href="/report-designer/designer?template=lab_result" target="_blank">
  Edit Template
</a>
```

Use the LIS identifiers your app already understands, such as `order_id`, `rhid`, `patient_id`, or `template_id`.

## Data Provider Pattern

```python
def report_data_provider(template_id, request_args, request_json):
    order_id = request_args.get("order_id")
    rhid = request_args.get("rhid")
    return load_lis_report_data(template_id=template_id, order_id=order_id, rhid=rhid)

designer = SlimReportDesigner(
    template_provider=template_provider,
    data_provider=report_data_provider,
)
```

The package does not own LIS SQL. Keep database access in the app and return plain dictionaries to the renderer.

## Permissions

Recommended LIS policy:

- Patients: no designer access, no staff-only print/export routes
- Staff: preview and export result templates
- Admin/supervisor: edit and save templates

Configure `auth_required`, `can_view_template`, `can_export_template`, and `can_edit_template` in the Flask extension.

## Template Selection

Use `GET /report-designer/api/templates` to populate dropdowns. Template summaries include IDs and metadata from the configured provider.

## Troubleshooting

- Blank or missing data: confirm the query string reaches `data_provider`.
- Wrong template: confirm the saved template ID in the URL.
- Unsafe filename: use `filename_provider` or `filename=...`; names are sanitized automatically.
- Permission denied: check auth and permission hook return values.
- PDF errors: request the same URL with `Accept: application/json` to receive a structured error response.
