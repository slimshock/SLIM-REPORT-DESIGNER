# Flask Database Template Storage Example

This example stores Slim Report Designer templates in SQLite through the framework-agnostic
`SQLAlchemyTemplateProvider`.

## Run

From the repository root:

```bash
python -m pip install "git+https://github.com/slimshock/SLIM-REPORT-DESIGNER.git@develop#subdirectory=packages/slim_report_core"
python -m pip install SQLAlchemy
python -m pip install "git+https://github.com/slimshock/SLIM-REPORT-DESIGNER.git@develop#subdirectory=packages/slim_report_designer_ui"
python -m pip install "git+https://github.com/slimshock/SLIM-REPORT-DESIGNER.git@develop#subdirectory=packages/slim_report_flask"
python examples/flask_database_app/app.py
```

For local development from a clone, editable installs of the same package directories are also valid.
The app code imports installed packages directly and does not modify `sys.path`.

Open:

```text
http://127.0.0.1:5000/report-designer/designer
http://127.0.0.1:5000/report-designer/designer?template=complete_sprint5_lab_report
http://127.0.0.1:5000/report-designer/designer?template=complete_sprint5_lab_report&order_id=ORD-2026-0001
```

The app creates `examples/flask_database_app/report_templates.db` locally and seeds a few sample
templates from `examples/flask_app/sample_templates/`. The database file is ignored by git.

## What It Demonstrates

- Plain SQLAlchemy with SQLite.
- App-owned `ReportTemplate` model.
- `SQLAlchemyTemplateProvider`.
- Template seeding from filesystem JSON.
- Save enabled for designer edits.
- `data_provider` hook for request-specific `order_id` data.

The example intentionally does not contain LIS business logic. Real LIS apps should query their own
patient, order, result, user, and permission tables in the configured hooks.

See also:

- `docs/template-storage.md`
- `docs/lis-flask-template-storage.md`
- `docs/lis-integration-hardening.md`
