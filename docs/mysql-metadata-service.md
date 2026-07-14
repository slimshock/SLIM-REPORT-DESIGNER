# MySQL Read-Only Metadata Service

Sprint 7.4 adds framework-independent discovery of approved MySQL reporting views and their column
metadata. It reuses the Sprint 7.3 provider, including its verified read-only connection setup and
context-managed cleanup.

> **Security boundary:** The metadata service reads only `information_schema.VIEWS` and
> `information_schema.COLUMNS`. It does not execute a report view, execute custom dataset SQL, or
> fetch report rows. Production report users must still have the minimum required `SELECT`
> permissions and should be restricted to approved reporting views.

Some MySQL and MariaDB installations restrict `information_schema` visibility based on the current
account's privileges. A view that is not visible to the account is reported as not found.

## Usage

```python
from slim_report_core import (
    DataSourceProviderRegistry,
    MetadataAccessPolicy,
    MySQLDataSourceProvider,
    MySQLMetadataService,
)

registry = DataSourceProviderRegistry()
registry.register(MySQLDataSourceProvider())
provider = registry.get("mysql")

metadata = MySQLMetadataService(
    provider=provider,
    policy=MetadataAccessPolicy(
        allowed_view_prefixes=("report_",),
    ),
)

views = metadata.list_views(data_source)
for view in views:
    print(view.view_name)

schema = metadata.inspect_view(data_source, "report_patient_results")
for column in schema.columns:
    print(
        column.name,
        column.database_type,
        column.normalized_type,
        column.nullable,
    )
```

This workflow fetches metadata rows only. `inspect_view()` verifies the object through
`information_schema.VIEWS` before reading its `information_schema.COLUMNS` records, and both steps
share one provider-owned connection.

## Views-Only Behavior

The service lists from `information_schema.VIEWS`; it never falls back to `TABLES`. Base tables,
temporary tables, procedures, functions, triggers, events, and stored routines are outside Sprint
7.4. Setting `views_only=False` raises `UnsupportedMetadataOperationError` rather than silently
broadening access.

The default policy searches only the configured `MySQLConnectionConfig.database`. System schemas
(`information_schema`, `mysql`, `performance_schema`, and `sys`) and cross-schema identifiers are
blocked by default.

## Approved-View Filtering

Exact and prefix allowlists can be combined:

```python
policy = MetadataAccessPolicy(
    allowed_view_names=("report_daily_sales",),
    allowed_view_prefixes=("report_", "vw_report_"),
)
```

Matching is case-insensitive in Python, while returned metadata preserves the database's original
name. A view is allowed when it matches an exact name or an allowed prefix. Empty allowlists permit
all views in the configured schema, subject to the other policy restrictions.

Listing filters disallowed views. Direct inspection conceals both missing and disallowed views as
`ViewNotFoundError`, preventing the API from confirming that a blocked object exists. Policy
filtering is always repeated in Python even though schema filtering also occurs in SQL.

## Identifiers and Cross-Schema Access

Logical view identifiers use the project's strict identifier form: each segment starts with a
letter or underscore and contains only letters, digits, and underscores. SQL fragments, comments,
semicolons, backtick quoting, path syntax, dollar signs, and identifiers with more than two segments
are rejected.

Unqualified names resolve against the configured database. Qualified identifiers require both
`allow_cross_schema=True` and an exact case-insensitive match in `allowed_schemas`:

```python
policy = MetadataAccessPolicy(
    allow_cross_schema=True,
    allowed_schemas=("archive",),
)
```

An empty cross-schema allowlist is invalid. System schemas remain blocked unless
`include_system_schemas=True` is also explicitly set. Schema and view values are passed as PyMySQL
parameters; they are never concatenated into metadata SQL, and the active database is not changed.

## Metadata Models and Limits

`DatabaseViewInfo`, `DatabaseColumnInfo`, and `DatabaseViewSchema` are immutable and contain no
cursor, connection, credential, or driver object. Definer, security type, and updatable state are
cleared by default; enable them deliberately with `include_updatable_metadata=True`.

The default limits are 1,000 views and 1,000 columns per view. Queries request one record beyond the
limit so the service can detect incomplete metadata. Exceeding a limit raises
`MetadataLimitExceededError`; results are never silently truncated. Limits and policy identifiers
are validated when the immutable policy is created.

## MySQL Type Normalization

The original `COLUMN_TYPE` string is preserved as `database_type`. `MySQLTypeMapper` independently
normalizes fields to the Sprint 7.1 types:

| MySQL/MariaDB family | Report type |
| --- | --- |
| Character, text, enum, set, JSON | `string` |
| Integer and year | `integer` |
| `tinyint(1)` | `boolean` |
| Float, double, real | `float` |
| Decimal and numeric | `decimal` |
| Bool and boolean | `boolean` |
| Date | `date` |
| Time | `time` |
| Datetime and timestamp | `datetime` |
| Binary, blobs, and bit | `binary` |
| Geometry and unknown future types | `unknown` |

`bit(1)` remains `binary`; only the explicit `tinyint(1)` display-width convention is normalized to
`boolean`. Mapping is case-insensitive, deterministic, independent from PyMySQL, and tolerant of
future types.

## Errors and Resource Lifecycle

Metadata permission failures, invalid rows, limits, missing views, and invalid identifiers use
focused project exceptions. Connection timeout, connection loss, unknown-database, missing-driver,
and read-only setup failures reuse the Sprint 7.3 exception hierarchy where appropriate. Raw driver
exceptions and credential-bearing connection details are not exposed or logged.

Every operation obtains a new connection through `provider.connection(data_source)`. Every metadata
cursor closes after success or failure, and the provider closes the connection. The service retains
only the provider, immutable policy, and stateless type mapper—never a live connection or cursor.
