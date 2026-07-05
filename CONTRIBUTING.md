# Contributing

Thank you for considering a contribution to Slim Report Designer.

## Project Direction

Slim Report Designer is built around a framework-agnostic core. The core package must remain independent from Flask, Django, FastAPI, SQLAlchemy, and other application frameworks. Framework-specific behavior belongs in adapter packages.

Before proposing major features, read:

- `docs/principles.md`
- `docs/decisions/`

## Development Setup

```bash
python -m pip install -e packages/slim_report_core
python -m pip install -e packages/slim_report_flask
python -m pip install pytest
pytest
```

## Contribution Guidelines

- Keep changes small and focused.
- Add or update tests for behavior changes.
- Document public APIs as they are introduced.
- Prefer explicit configuration over hidden behavior.
- Preserve backward compatibility once public APIs are released.

## Pull Requests

Pull requests should include:

- A clear description of the change.
- Tests or a rationale when tests are not applicable.
- Documentation updates for public behavior.
- Notes about compatibility or migration impact, if any.

