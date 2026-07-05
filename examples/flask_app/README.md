# Flask Example

This example demonstrates the current working flow:

- load a JSON report template into `Report`
- create the sample template with `Report` if the JSON file is missing
- resolve data from a Flask provider
- preview as HTML
- export as PDF
- edit and save JSON from the built-in designer page

The JSON editor is an interim designer interface. Flask storage returns `Report`, and routes render
through `slim_report_core`; Flask does not own rendering logic.

Included demo templates:

- `lab_result`: compact laboratory result
- `cerebro_cbc`: CBC report styled after the Cerebro Diagnostic System sample

## Run

From the repository root:

```bash
python -m pip install -e packages/slim_report_core
python -m pip install -e packages/slim_report_flask
python examples/flask_app/app.py
```

## Routes

```text
http://127.0.0.1:5000/report-designer/templates/lab_result/designer
http://127.0.0.1:5000/report-designer/templates/lab_result/preview/sample
http://127.0.0.1:5000/report-designer/templates/lab_result/export/pdf/sample
http://127.0.0.1:5000/direct-preview/ORDER-1001
http://127.0.0.1:5000/direct-export/pdf/ORDER-1001
http://127.0.0.1:5000/report-designer/templates/cerebro_cbc/designer
http://127.0.0.1:5000/report-designer/templates/cerebro_cbc/preview/43
http://127.0.0.1:5000/report-designer/templates/cerebro_cbc/export/pdf/43
http://127.0.0.1:5000/direct-preview/cerebro_cbc/43
http://127.0.0.1:5000/direct-export/pdf/cerebro_cbc/43
```

The providers are registered in `app.py` as `lab_result` and `cerebro_cbc`. The sample templates are
stored in `sample_templates/`.

The adapter-level flow is:

```text
Flask route -> TemplateStore.load_report() -> Report -> render_html/render_pdf -> response
```

The direct routes in `app.py` show the same boundary without the adapter route wrapper:

```python
report = designer.get_report("lab_result")
data = lab_result(record_id)
html = report.render_html(data)
pdf_bytes = report.render_pdf(data)
```

The checked-in JSON file is still the persistence format for the demo. The report definition in
`create_lab_result_report()` is there so the example can be recreated from the beginner-friendly
`Report` API.
