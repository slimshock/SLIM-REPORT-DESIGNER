# Flask Production Integration

Slim Report Designer can be plugged into an existing Flask app through `SlimReportDesigner`.
The Flask adapter hosts the static designer UI, template APIs, HTML preview, and PDF export.

## Install

From a source checkout, install the package folders you need:

```bash
python -m pip install -e packages/slim_report_core
python -m pip install -e packages/slim_report_designer_ui
python -m pip install -e packages/slim_report_flask
```

## Basic Setup

```python
from flask import Flask
from slim_report_core.storage import FileSystemTemplateProvider
from slim_report_flask import SlimReportDesigner

app = Flask(__name__)
designer = SlimReportDesigner(
    app,
    template_provider=FileSystemTemplateProvider("sample_templates", allow_save=True),
)
```

## App Factory Setup

```python
def create_app():
    app = Flask(__name__)
    designer = SlimReportDesigner(
        template_provider=FileSystemTemplateProvider("sample_templates", allow_save=False),
        url_prefix="/admin/reports",
    )
    designer.init_app(app)
    return app
```

With `url_prefix="/admin/reports"`, routes are served under:

```text
/admin/reports/designer
/admin/reports/api/templates
/admin/reports/api/templates/<template_id>
/admin/reports/api/preview
/admin/reports/api/export/pdf
```

## Template Provider

`TemplateProvider` is the framework-agnostic storage interface in `slim_report_core.storage`:

```python
class TemplateProvider:
    def list_templates(self): ...
    def get_template(self, template_id): ...
    def save_template(self, template_id, template): ...
    def exists(self, template_id): ...
```

`FileSystemTemplateProvider` reads and writes `.json` templates from a directory. It validates
template ids and prevents path traversal. Use `allow_save=False` when templates should be
read-only in production.

Database-backed Flask apps can use `SQLAlchemyTemplateProvider` with an app-owned model:

```python
from slim_report_core.storage import SQLAlchemyTemplateProvider

provider = SQLAlchemyTemplateProvider(
    session=db.session,
    model=ReportTemplate,
    allow_save=True,
)

designer = SlimReportDesigner(
    template_provider=provider,
    data_provider=data_provider,
)
```

## Data Provider

Use `data_provider` to resolve report data from your LIS, EHR, or app services:

```python
def data_provider(template_id, request_args, request_json):
    order_id = request_args.get("order_id") or request_json.get("order_id")
    return load_order_report_data(order_id)

designer = SlimReportDesigner(
    template_provider=FileSystemTemplateProvider("templates"),
    data_provider=data_provider,
)
```

Preview/export data priority is:

1. Explicit `data` in the request body.
2. `data_provider`.
3. Provider sample data.
4. `template.data.sample`.
5. Empty dict.

## Auth And Permissions

The Flask adapter does not depend on Flask-Login. Pass callbacks from your app:

```python
designer = SlimReportDesigner(
    template_provider=FileSystemTemplateProvider("templates"),
    auth_required=lambda: current_user.is_authenticated,
    can_view_template=lambda template_id: current_user.can("view_reports"),
    can_edit_template=lambda template_id: current_user.can("edit_reports"),
    can_export_template=lambda template_id: current_user.can("export_reports"),
)
```

Unauthorized requests return 401. Permission failures return 403.

## CSRF

The adapter does not force a CSRF dependency. If your app uses CSRF tokens, provide a token and
header name:

```python
designer = SlimReportDesigner(
    template_provider=FileSystemTemplateProvider("templates"),
    csrf_header_name="X-CSRFToken",
    csrf_token_provider=lambda: session.get("csrf_token"),
)
```

The designer frontend includes that header on save, preview, and PDF export POST requests.

## Static Assets And Reverse Proxies

Designer HTML, CSS, and JavaScript are served from packaged `slim_report_designer_ui` resources.
The Flask-rendered page injects `window.SLIM_REPORT_CONFIG.apiBase`, so custom prefixes and reverse
proxy subpaths work when Flask URL generation is configured correctly.

## Troubleshooting

- Missing JS/CSS usually means `slim_report_designer_ui` is not installed or importable.
- 401 means your `auth_required` hook returned false.
- 403 means a permission hook blocked the operation.
- Save failures with read-only templates usually mean `FileSystemTemplateProvider(..., allow_save=False)`.
- SQLAlchemy provider import errors usually mean the optional extra was not installed.
- Preview/PDF failures return JSON with `ok: false`, `error`, and `error_detail`.
