# Designer Static Server

This example serves the framework-agnostic designer UI without Flask, Django, FastAPI, or any backend adapter.

## Run

From the repository root:

```bash
python examples/designer_static_server/serve.py
```

Open:

```text
http://127.0.0.1:8008/
```

## What Works In Static Mode

- Visual designer canvas
- JSON import/export
- Local browser version history
- Editing `data.sample`
- Editing/preserving `data.fields`
- Placeholder/sample data canvas toggle

## Limitation

Static mode does not export PDF without a backend API. Use the Flask example when you need preview/export integration.
