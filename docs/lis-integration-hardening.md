# LIS Integration Hardening

Sprint 6.3 focuses on using Slim Report Designer inside an existing Flask LIS app that owns its
database, authentication, permissions, and report data queries.

Do not expose the designer to patient portal users. Treat the designer as a staff/admin tool.

## Install From GitHub

Slim Report Designer is a multi-package repository. Install the package folders, not the repository
root:

```bash
pip uninstall -y slim-report-core slim-report-flask slim-report-designer-ui UNKNOWN

pip install "git+https://github.com/slimshock/SLIM-REPORT-DESIGNER.git@develop#subdirectory=packages/slim_report_core"
pip install "git+https://github.com/slimshock/SLIM-REPORT-DESIGNER.git@develop#subdirectory=packages/slim_report_designer_ui"
pip install "git+https://github.com/slimshock/SLIM-REPORT-DESIGNER.git@develop#subdirectory=packages/slim_report_flask"
```

Verify that imports resolve from `site-packages`, not from a local checkout:

```bash
python -c "import slim_report_flask; print(slim_report_flask.__file__)"
python -c "import slim_report_core; import slim_report_flask; import slim_report_designer_ui; print('OK')"
python -c "from slim_report_flask import SlimReportDesigner; print('OK Flask')"
python -c "from slim_report_core.storage import FileSystemTemplateProvider, SQLAlchemyTemplateProvider, PyMySQLTemplateProvider; print('OK storage')"
```

If the printed path points at a local `D:\...SLIM-REPORT-DESIGNER...` checkout in production, remove
local `sys.path.insert(...)` code and reinstall the packages into the LIS virtual environment.

## Remove Development Path Hacks

Production LIS code should import installed packages directly:

```python
from slim_report_flask import SlimReportDesigner
from slim_report_core.storage import FileSystemTemplateProvider, PyMySQLTemplateProvider
```

Remove development-only patterns from production code:

```python
SLIM_REPORT_DESIGNER_ROOT = "..."
SLIM_REPORT_TEMPLATE_DIR = "..."
_add_slim_report_designer_source_paths()
sys.path.insert(...)
```

Local repository examples may still use repository template files as sample data, but production LIS
apps should use their own template directory or database table.

## PyMySQL Template Storage

`PyMySQLTemplateProvider` is dependency-free. It does not import PyMySQL. Your LIS provides a
connection factory:

```python
from slim_report_core.storage import PyMySQLTemplateProvider

def get_mysql_connection():
    # Return your app's PyMySQL connection or pooled connection.
    # Do not put credentials in Slim Report Designer config.
    return mysql_connection

provider = PyMySQLTemplateProvider(
    get_mysql_connection,
    table_name="report_templates",
    allow_save=True,
    allow_delete=False,
    auto_ping=True,
)
```

When `auto_ping=True`, the provider calls `conn.ping(reconnect=True)` when the connection supports
it. If the connection is missing or stale, Flask APIs return a clean storage error instead of a
traceback.

## Table Schema

Create the table in your LIS migration system. The provider never creates tables automatically
unless you explicitly call `provider.ensure_schema()`.

```sql
CREATE TABLE IF NOT EXISTS report_templates (
    id INT AUTO_INCREMENT PRIMARY KEY,
    template_id VARCHAR(120) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    description TEXT NULL,
    category VARCHAR(120) NULL,
    template_json LONGTEXT NOT NULL,
    sample_data_json LONGTEXT NULL,
    version INT NOT NULL DEFAULT 1,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME NULL,
    updated_at DATETIME NULL,
    INDEX idx_report_templates_template_id (template_id),
    INDEX idx_report_templates_active (is_active)
);
```

You can also inspect the SQL from Python:

```python
print(PyMySQLTemplateProvider.create_table_sql())
```

## Flask LIS Setup

Keep patient/order/result queries in your LIS app. The designer receives data through hooks:

```python
from flask import session
from slim_report_flask import SlimReportDesigner
from slim_report_core.storage import PyMySQLTemplateProvider
from utils.db import get_mysql_connection

def lis_report_data_provider(template_id, request_args, request_json):
    order_id = request_args.get("order_id") or (request_json or {}).get("order_id")
    if not order_id:
        return {}

    # App-specific LIS logic goes here.
    # Do not put LIS SQL/business rules inside Slim Report Designer.
    return build_lab_report_data(order_id)

report_designer = SlimReportDesigner(
    template_provider=PyMySQLTemplateProvider(
        get_mysql_connection,
        allow_save=True,
        allow_delete=False,
    ),
    data_provider=lis_report_data_provider,
    url_prefix="/report-designer",
    auth_required=lambda: bool(session.get("user_id")) and not session.get("patient_id"),
    can_view_template=lambda template_id: bool(session.get("user_id")),
    can_edit_template=lambda template_id: session.get("role") == "admin",
    can_export_template=lambda template_id: bool(session.get("user_id")),
)

report_designer.init_app(app)
```

If your LIS has a central permission function, use it:

```python
can_edit_template=lambda template_id: has_permission("report_template_edit")
```

## Auth And Save Policy

Recommended production policy:

- Patients cannot access `/report-designer/*`.
- Authenticated staff may view templates.
- Admin or supervisor users may save templates.
- Export is staff-only.
- Keep `allow_save=False` until the LIS permission hooks are verified.
- Keep `allow_delete=False` unless your app explicitly wants soft-delete from the designer.

`delete_template()` on the PyMySQL provider performs a soft delete by setting `is_active=0`.

## Data Provider Pattern

Use request arguments or JSON payload fields to choose the LIS record:

```python
def lis_report_data_provider(template_id, request_args, request_json):
    order_id = request_args.get("order_id")
    if not order_id and isinstance(request_json, dict):
        order_id = request_json.get("order_id")
    if not order_id:
        return {}
    return build_lab_report_data(order_id)
```

Return ordinary JSON-compatible dictionaries. Image/signature fields may be empty strings, `None`,
`"null"`, `"undefined"`, or unresolved placeholders; preview/PDF export will render those image
slots blank instead of printing `Image`.

## Sample Templates

LIS-oriented sample templates live in:

```text
examples/lis_templates/lab_result_hematology.json
examples/lis_templates/lab_result_hematology_two_column.json
```

The two-column sample uses two table objects bound to `left_results` and `right_results`. It does
not implement automatic multi-column detail flow; that belongs to the later advanced table work.

Expected data shape:

```json
{
  "clinic": {},
  "patient": {},
  "order": {},
  "department": {},
  "left_results": [],
  "right_results": [],
  "results": []
}
```

## Clean Error Responses

Provider failures return JSON with a stable code:

```json
{
  "ok": false,
  "error_detail": {
    "code": "template_storage_error",
    "message": "Could not connect to MySQL."
  }
}
```

The response also keeps the legacy top-level `error` string for older clients.

## Troubleshooting

- `ModuleNotFoundError`: reinstall the three subpackages into the LIS venv.
- Imports resolve from the local checkout: remove `sys.path.insert(...)` hacks.
- `UNKNOWN` package appears: uninstall it with `pip uninstall -y UNKNOWN`; use subpackage installs.
- Designer loads but templates do not: check `report_templates.is_active=1` and `template_id`.
- Save fails: confirm `allow_save=True` and `can_edit_template(...)` returns `True`.
- MySQL goes stale: keep `auto_ping=True` and return a valid PyMySQL connection from the factory.
- Empty signature slots show text: reinstall the current packages and confirm preview HTML does not
  contain `>Image<`.
