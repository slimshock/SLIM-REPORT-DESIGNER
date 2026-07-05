# Designer Static Server

This example serves the framework-agnostic designer UI without Flask, Django, FastAPI, or any
backend adapter.

```bash
python examples/designer_static_server/serve.py
```

Open:

```text
http://127.0.0.1:8008/
```

In this mode the designer uses local browser storage. Preview opens a local HTML preview, JSON
import/export works, and PDF export requires a backend API.
