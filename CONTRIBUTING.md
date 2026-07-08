# Contributing

Thank you for considering a contribution to Slim Report Designer.

## Project Direction

Slim Report Designer is built around a framework-agnostic core. The core package must remain independent from Flask, Django, FastAPI, SQLAlchemy, and other application frameworks. Framework-specific behavior belongs in adapter packages.

The project is still early alpha. Keep changes small, documented, and easy to review.

Before proposing major features, read:

- `docs/principles.md`
- `docs/architecture.md`
- `docs/roadmap.md`
- `docs/decisions/`

## Development Setup

```bash
python -m pip install -e packages/slim_report_core
python -m pip install -e packages/slim_report_designer_ui
python -m pip install -e packages/slim_report_flask
python -m pip install -e packages/slim_report_cli
python -m pip install pytest ruff
python -m pytest
python -m ruff check packages tests
```

## Contribution Guidelines

- Keep changes small and focused.
- Keep `slim_report_core` independent from Flask, Django, FastAPI, databases, and web framework code.
- Keep the designer UI framework-agnostic.
- Do not add a frontend build step.
- Do not introduce React or Vue unless the project direction changes later.
- Add or update tests for behavior changes.
- Update docs when public behavior changes.
- Preserve JSON backward compatibility where practical.
- Prefer explicit configuration over hidden behavior.
- Do not rewrite sample templates unnecessarily.

## Pull Requests

Pull requests should include:

- A clear description of the change.
- Tests or a rationale when tests are not applicable.
- Documentation updates for public behavior.
- Notes about compatibility or migration impact, if any.
