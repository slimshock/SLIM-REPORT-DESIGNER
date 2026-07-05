# Pure Python Example

The pure Python example creates a report template without a web framework.

```bash
python examples/pure_python/create_report.py
```

For rendering, use the public core API:

```python
from slim_report_core.serialization import JSONSerializer

report = JSONSerializer().load("template.json")
html = report.render_html(data)
pdf_bytes = report.render_pdf(data)
```
