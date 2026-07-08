# Flask Production Integration Example

This example shows the Sprint 6 Flask extension API in an app-factory style setup.

## Run

From the repository root:

```bash
python -m pip install -e packages/slim_report_core
python -m pip install -e packages/slim_report_designer_ui
python -m pip install -e packages/slim_report_flask
python examples/flask_production_app/app.py
```

Open:

```text
http://127.0.0.1:5001/admin/reports/designer?template=complete_sprint5_lab_report&order_id=ORD-2026-0001
```

## What It Demonstrates

- `create_app()` app factory pattern.
- `SlimReportDesigner(...).init_app(app)`.
- Core `FileSystemTemplateProvider` using existing JSON sample templates.
- Custom URL prefix: `/admin/reports`.
- `data_provider` hook for LIS-style `order_id` data resolution.
- `auth_required` hook.
- `can_view_template`, `can_edit_template`, and `can_export_template` hooks.
- Save disabled through `FileSystemTemplateProvider(..., allow_save=False)`.
- CSRF header/token config injection for frontend POST requests.

Use `?auth=0` on a designer URL to see the demo authentication hook return 401.
