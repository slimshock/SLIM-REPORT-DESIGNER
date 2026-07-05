# Slim Report Designer

Slim Report Designer is an open-source, framework-agnostic reporting platform for Python applications. It provides a JSON-based report engine, pluggable widgets, multiple exporters, and framework adapters starting with Flask.

This repository is the project foundation. It intentionally avoids full feature implementation while establishing the package layout, documentation surface, and architectural boundaries for future development.

## Goals

- Keep the reporting core independent from web frameworks, ORMs, and application stacks.
- Provide a stable JSON-based report definition format.
- Support pluggable widgets, exporters, data providers, and storage backends.
- Ship framework adapters without making any framework the foundation of the project.
- Start with first-class Flask support and leave clear extension points for Django, FastAPI, CLI, and pure Python usage.

## Packages

| Package | Purpose |
| --- | --- |
| `slim_report_core` | Framework-agnostic report engine, schemas, widgets, exporters, and extension interfaces. |
| `slim_report_flask` | Flask adapter package. |
| `slim_report_django` | Future Django adapter package. |
| `slim_report_fastapi` | Future FastAPI adapter package. |
| `slim_report_cli` | Future command-line tools. |

## Architecture Rule

`slim_report_core` must never import Flask, Django, FastAPI, SQLAlchemy, or any web framework.

Framework integrations belong in adapter packages under `packages/`. The core package should remain usable from Flask, Django, FastAPI, command-line tools, desktop applications, background workers, scheduled jobs, and pure Python applications.

## Repository Layout

```text
packages/
  slim_report_core/
  slim_report_flask/
  slim_report_django/
  slim_report_fastapi/
  slim_report_cli/
examples/
  pure_python/
  flask_app/
  django_app/
  fastapi_app/
  lis_demo/
  pos_demo/
docs/
tests/
scripts/
```

## Development

This repository uses a Python `src/` layout for each package and shared tool configuration in the root `pyproject.toml`.

```bash
python -m pip install -e packages/slim_report_core
python -m pip install -e packages/slim_report_flask
python -m pip install pytest
pytest
```

Additional package-specific dependencies will be added as the adapters become functional.

## Status

Early foundation. APIs are not stable yet.

# Changelog

## v0.1.0-alpha.2

### Added

- HTML Preview Renderer
- PDF Renderer
- Flask Preview Routes
- PDF Export Route
- Sample Laboratory Report