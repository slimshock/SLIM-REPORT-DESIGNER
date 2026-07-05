# Flask Example

This example demonstrates the current working flow:

- load a JSON report template into `Report`
- resolve data from a Flask provider
- preview as HTML
- export as PDF
- edit and save JSON from the built-in designer page

The JSON editor is an interim designer interface. Flask storage returns `Report`, and routes render
through `slim_report_core`; Flask does not own rendering logic.

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
```

The provider is registered in `app.py` as `lab_result`. The sample template is stored in `sample_templates/lab_result.json`.

The adapter-level flow is:

```text
Flask route -> TemplateStore.load_report() -> Report -> render_html/render_pdf -> response
```
