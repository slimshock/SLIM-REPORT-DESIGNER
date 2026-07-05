# Pure Python Example

The pure Python example creates a report template without a web framework.

```bash
python examples/pure_python/create_report.py
```

For rendering, use the public core API:

```python
from slim_report_core import Report

report = Report.load_json("template.json")
html = report.render_html(data)
pdf_bytes = report.render_pdf(data)
```
