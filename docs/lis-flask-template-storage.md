# LIS Flask Template Storage

Slim Report Designer can be embedded in a LIS Flask app without putting LIS business rules inside
the designer. The LIS owns patients, orders, results, users, permissions, and data queries. Slim
Report Designer owns template JSON storage, sample data storage, rendering, and designer routes.

## Recommended Setup

```python
from flask_login import current_user

from slim_report_core.storage import SQLAlchemyTemplateProvider
from slim_report_flask import SlimReportDesigner

template_provider = SQLAlchemyTemplateProvider(
    session=db.session,
    model=ReportTemplate,
)

def lis_report_data_provider(template_id, request_args, request_json):
    order_id = request_args.get("order_id") or request_json.get("order_id")
    if not order_id:
        return {}

    return {
        "patient": {"name": "Juan Dela Cruz", "sex": "M", "age": "35"},
        "order": {"order_id": order_id, "date": "2026-07-09"},
        "results": [
            {"test_name": "WBC", "result": "7.2", "unit": "10^9/L", "flag": "N"}
        ],
    }

designer = SlimReportDesigner(
    template_provider=template_provider,
    data_provider=lis_report_data_provider,
    can_edit_template=lambda template_id: current_user.role == "admin",
)

designer.init_app(app)
```

## Table Model

Applications own migrations and can adapt the field names. A typical Flask-SQLAlchemy model:

```python
class ReportTemplate(db.Model):
    __tablename__ = "report_templates"

    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.String(120), unique=True, nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(120), nullable=True)
    template_json = db.Column(db.JSON, nullable=False)
    sample_data_json = db.Column(db.JSON, nullable=True)
    version = db.Column(db.Integer, default=1, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_by = db.Column(db.String(120), nullable=True)
    updated_by = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=True)
```

For MySQL 5.6 or other databases without JSON columns, use Text fields:

```python
template_json_text = db.Column(db.Text, nullable=False)
sample_data_json_text = db.Column(db.Text, nullable=True)

template_provider = SQLAlchemyTemplateProvider(
    session=db.session,
    model=ReportTemplate,
    template_field="template_json_text",
    sample_data_field="sample_data_json_text",
    json_dumps=json.dumps,
    json_loads=json.loads,
)
```

## Permissions

Normal LIS users usually preview/export only. Admin or template-designer users can save.

```python
designer = SlimReportDesigner(
    template_provider=template_provider,
    auth_required=lambda: current_user.is_authenticated,
    can_view_template=lambda template_id: current_user.can("reports.view"),
    can_edit_template=lambda template_id: current_user.can("reports.design"),
    can_export_template=lambda template_id: current_user.can("reports.export"),
)
```

If saves must be disabled globally, set `allow_save=False` on the provider.

## Routes

With the default prefix:

```text
/report-designer/designer?template=complete_sprint5_lab_report&order_id=ORD-2026-0001
/report-designer/api/templates
/report-designer/api/templates/<template_id>
/report-designer/api/preview
/report-designer/api/export/pdf
```

Production apps often use a custom prefix:

```python
designer = SlimReportDesigner(
    template_provider=template_provider,
    data_provider=lis_report_data_provider,
    url_prefix="/admin/reports",
)
```

## Preview And PDF Data

Preview and PDF export use the same data resolution order:

1. Explicit request data.
2. `data_provider`.
3. Provider sample data.
4. Embedded `template.data.sample`.
5. Empty dict.

This lets template designers preview with sample data while production preview/export uses the LIS
order, patient, and result queries supplied by the host app.

## Example App

Run the SQLite database example:

```bash
python examples/flask_database_app/app.py
```

Open:

```text
http://127.0.0.1:5000/report-designer/designer?template=complete_sprint5_lab_report&order_id=ORD-2026-0001
```
