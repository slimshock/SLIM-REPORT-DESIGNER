# Template Storage

Slim Report Designer stores report templates through a framework-agnostic provider interface in
`slim_report_core.storage`. Framework adapters, including Flask, call this interface for list,
load, save, delete, preview, and export workflows.

Preferred imports:

```python
from slim_report_core.storage import (
    FileSystemTemplateProvider,
    SQLAlchemyTemplateProvider,
    TemplateProvider,
)
```

Compatibility imports from `slim_report_flask` still work.

## Provider Contract

Providers implement:

```python
class TemplateProvider:
    def list_templates(self) -> list[dict]: ...
    def get_template(self, template_id: str) -> dict: ...
    def save_template(self, template_id: str, template: dict) -> dict: ...
    def exists(self, template_id: str) -> bool: ...
    def delete_template(self, template_id: str) -> bool: ...
```

Template summaries use a predictable metadata shape:

```python
{
    "id": "lab_result",
    "name": "Lab Result",
    "description": "Main laboratory result form",
    "category": "laboratory",
    "version": 1,
    "is_active": True,
    "created_at": None,
    "updated_at": None,
}
```

## Template IDs

Template IDs are validated before filesystem or database access. Allowed IDs match:

```text
^[A-Za-z0-9_.-]+$
```

Examples: `lab_result`, `complete_sprint5_lab_report`, `receipt-v1`, `hematology.result`.

Rejected examples: `../secret`, `../../app.py`, `C:\secret`, `folder/template`,
`template.json/other`, and empty strings.

## FileSystemTemplateProvider

`FileSystemTemplateProvider` reads and writes JSON files from a configured directory.

```python
from slim_report_core.storage import FileSystemTemplateProvider

provider = FileSystemTemplateProvider(
    "sample_templates",
    allow_save=False,
    allow_delete=False,
)
template = provider.get_template("lab_result")
```

`lab_result` resolves to `lab_result.json`; callers should not pass `.json`. Saves and deletes are
blocked unless explicitly enabled. Non-JSON files are ignored during listing.

## SQLAlchemyTemplateProvider

`SQLAlchemyTemplateProvider` works with plain SQLAlchemy sessions and Flask-SQLAlchemy-style
sessions. SQLAlchemy is optional; normal `slim_report_core` imports do not require it.

```python
from slim_report_core.storage import SQLAlchemyTemplateProvider

provider = SQLAlchemyTemplateProvider(
    session=db.session,
    model=ReportTemplate,
    allow_save=True,
    allow_delete=False,
)
```

The provider maps to fields by name, so applications can keep their own model:

```python
provider = SQLAlchemyTemplateProvider(
    session=db.session,
    model=ReportTemplate,
    template_field="template_json_text",
    sample_data_field="sample_data_json_text",
    json_dumps=json.dumps,
    json_loads=json.loads,
)
```

Use the `sqlalchemy` extra when installing from this repository:

```bash
python -m pip install -e "packages/slim_report_core[sqlalchemy]"
```

## Sample Data

Sample data may come from:

1. Explicit `data` in a preview/export request.
2. Flask `data_provider`.
3. Provider sample data through `get_sample_data(template_id)`.
4. Embedded `template.data.sample`.
5. Empty dict.

Filesystem storage reads embedded `template.data.sample`. SQLAlchemy storage can store sample data
separately in `sample_data_json` or `sample_data_json_text`.

## Errors

Storage errors are defined in `slim_report_core.storage`:

- `TemplateStorageError`
- `TemplateNotFoundError`
- `TemplateExistsError`
- `TemplateValidationError`
- `TemplatePermissionError`
- `TemplateIdError`

Flask converts these to JSON API errors without stack traces.

## Custom Providers

Apps can implement `TemplateProvider` directly for S3, internal APIs, document stores, or custom
database layers. Keep application business logic outside the storage provider: the provider owns
template JSON, metadata, and sample data only.

## Troubleshooting

- `invalid_template_id`: the ID contains unsafe characters or path traversal.
- `template_not_found`: the safe ID does not exist in the provider.
- `forbidden`: save/delete is disabled or a permission hook blocked the request.
- SQLAlchemy import errors: install `packages/slim_report_core[sqlalchemy]`.
- MySQL 5.6 or databases without JSON columns: use Text fields plus `json_dumps`/`json_loads`.
