# Pure Python Example

The pure Python example creates a report without a web framework or JSON template.

```bash
python examples/pure_python/create_report.py
```

For direct rendering, use the public `Report` API:

```python
from slim_report_core import Report

report = Report("Demo")
page = report.page()
page.text("Hello", x=50, y=40)
page.field("patient.name", x=50, y=80)

html = report.render_html({"patient": {"name": "Juan Dela Cruz"}})
pdf_bytes = report.render_pdf({"patient": {"name": "Juan Dela Cruz"}})
```

Use `JSONSerializer` only when loading or saving a template file:

```python
from slim_report_core.serialization import JSONSerializer

report = JSONSerializer().load("template.json")
JSONSerializer().save(report, "template.json")
```
