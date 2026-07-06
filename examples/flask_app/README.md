# Flask Example

This example demonstrates the Flask-hosted designer and the core rendering flow:

- load JSON templates from `sample_templates/`
- open the framework-agnostic visual designer
- resolve sample/provider data
- preview as HTML
- export as PDF
- demonstrate repeating Detail rows
- demonstrate basic pagination for repeated rows and tables
- demonstrate barcode and QR objects

Flask does not own rendering. The adapter loads templates into `Report` and calls `slim_report_core`.

## Run

From the repository root:

```bash
python -m pip install -e packages/slim_report_core
python -m pip install -e packages/slim_report_designer_ui
python -m pip install -e packages/slim_report_flask
python examples/flask_app/app.py
```

## Designer URLs

```text
http://127.0.0.1:5000/report-designer/designer?template=lab_result
http://127.0.0.1:5000/report-designer/designer?template=cerebro_cbc
http://127.0.0.1:5000/report-designer/designer?template=repeating_lab_result
http://127.0.0.1:5000/report-designer/designer?template=table_lab_result
http://127.0.0.1:5000/report-designer/designer?template=barcode_qr_lab_result
```

## Preview And PDF

The visual designer can call the Flask API for preview and PDF export.

Direct example routes are also available:

```text
http://127.0.0.1:5000/report-designer/templates/lab_result/preview/sample
http://127.0.0.1:5000/report-designer/templates/lab_result/export/pdf/sample
http://127.0.0.1:5000/report-designer/templates/cerebro_cbc/preview/sample
http://127.0.0.1:5000/report-designer/templates/cerebro_cbc/export/pdf/sample
http://127.0.0.1:5000/report-designer/templates/repeating_lab_result/preview/sample
http://127.0.0.1:5000/report-designer/templates/repeating_lab_result/export/pdf/sample
http://127.0.0.1:5000/report-designer/templates/table_lab_result/preview/sample
http://127.0.0.1:5000/report-designer/templates/table_lab_result/export/pdf/sample
http://127.0.0.1:5000/report-designer/templates/barcode_qr_lab_result/preview/sample
http://127.0.0.1:5000/report-designer/templates/barcode_qr_lab_result/export/pdf/sample
```

## Templates

Sample templates are stored in:

```text
examples/flask_app/sample_templates/
```

Included templates:

- `lab_result`
- `cerebro_cbc`
- `repeating_lab_result`
- `table_lab_result`
- `barcode_qr_lab_result`

## Sample And Provider Data

The example registers provider functions in `app.py` with `@designer.provider("<template_id>")`.

Templates can also include `data.sample` for preview/export. The designer API preserves `data.fields` metadata for the Data Fields panel and binding picker.

## Repeating Detail Rows

`repeating_lab_result` demonstrates a Detail band with `repeat.enabled`, `repeat.data_path`, `repeat.row_height`, and row-relative field bindings such as `test`, `result`, `unit`, and `flag`. Its sample data includes enough rows to create multiple preview/PDF pages.

## Basic Table Object

`table_lab_result` demonstrates a single Table object bound to `results`, with editable columns for `test`, `result`, `unit`, `reference`, and `flag`. Its table rows continue onto additional pages and repeat the table header.

## Barcode And QR Objects

`barcode_qr_lab_result` demonstrates barcode and QR code objects bound to `order.id`. Preview and PDF export resolve provider/sample data first and fall back to literal object values when no bound value is available.
