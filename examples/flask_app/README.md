# Flask Example

This example demonstrates the current working flow:

- load a JSON report template into `Report`
- open the framework-agnostic Canvas designer UI
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
http://127.0.0.1:5000/report-designer/designer?template=lab_result
http://127.0.0.1:5000/report-designer/templates/lab_result/designer
http://127.0.0.1:5000/report-designer/templates/lab_result/preview/sample
http://127.0.0.1:5000/report-designer/templates/lab_result/export/pdf/sample
http://127.0.0.1:5000/report-designer/designer?template=cerebro_cbc
http://127.0.0.1:5000/report-designer/templates/cerebro_cbc/preview/43
http://127.0.0.1:5000/report-designer/templates/cerebro_cbc/export/pdf/43
```

The providers are registered in `app.py` as `lab_result` and `cerebro_cbc`. The sample templates are
stored in `sample_templates/`.

The adapter-level flow is:

```text
Flask route -> TemplateStore.load_report() -> Report -> render_html/render_pdf -> response
```

The Canvas designer flow is:

```text
Static designer UI -> /report-designer/api/* -> JSONSerializer -> Report -> preview/export/save
```
