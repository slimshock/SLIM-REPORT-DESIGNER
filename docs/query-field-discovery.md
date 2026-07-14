# Query Field Discovery

Query field discovery inspects the output fields of a query-backed `ReportDataset` without
executing a full report or returning row values.

It is intentionally a metadata-only workflow:

1. Validate the dataset SQL with `SQLValidator`.
2. Convert declared parameter values to Python values for driver binding.
3. Resolve a provider through `DataSourceProviderRegistry`.
4. Open the provider's verified read-only connection.
5. Execute the validated `SELECT` with bound parameters.
6. Read DB-API cursor metadata.
7. Fetch at most `QueryFieldDiscoveryPolicy.max_preview_rows`.
8. Return `DatasetField` definitions and close every cursor and connection.

## Example

```python
from datetime import date

from slim_report_core import (
    DataSourceProviderRegistry,
    MySQLDataSourceProvider,
    MySQLDialect,
    QueryFieldDiscoveryService,
    SQLValidator,
)

registry = DataSourceProviderRegistry()
registry.register(MySQLDataSourceProvider())

discovery = QueryFieldDiscoveryService(
    provider_registry=registry,
    sql_validator=SQLValidator(MySQLDialect()),
)

result = discovery.discover_fields(
    dataset=dataset,
    data_source=data_source,
    parameter_values={
        "date_from": date(2026, 1, 1),
        "date_to": date(2026, 12, 31),
    },
)

for field in result.fields:
    print(field.name, field.data_type)
```

`discover_fields()` does not mutate the dataset. Use `apply_fields(dataset, result)` when the caller
explicitly wants a copy of the dataset with discovered fields applied.

## Parameter Behavior

Sprint 7 query parameters use `:parameter_name` syntax. Parameter names are matched case-sensitively,
following the current SQL validator contract.

The service rejects:

- SQL parameters missing from `dataset.parameters`
- missing required discovery values
- invalid value conversions
- discovery values for unknown parameter names

Values are never interpolated into SQL. MySQL discovery converts validated named placeholders to
PyMySQL placeholders such as `%(date_from)s` and passes values separately to `cursor.execute()`.

Supported parameter value types are `string`, `integer`, `float`, `decimal`, `boolean`, `date`,
`time`, and `datetime`. Decimal values use `decimal.Decimal`; date/time values use the standard
`datetime` module types.

## Limits

`QueryFieldDiscoveryPolicy` defaults are deliberately small:

- `max_preview_rows=1`
- `max_columns=500`
- `max_query_length=100_000`
- `max_parameters=100`
- `execution_timeout_seconds=15`

Discovery uses cursor-side row limiting with `fetchmany(max_preview_rows)`. It does not append
`LIMIT 1` or wrap arbitrary SQL, because that can change semantics for CTEs, unions, comments, and
queries that already contain limits.

`fetchmany(1)` does not necessarily prevent the database server from fully processing a complex
query. Query timeout configuration, approved views, indexing, and reviewed SQL remain important.

## MySQL Type Mapping

MySQL DB-API type codes are mapped through the MySQL provider adapter and normalized to report field
types such as `string`, `integer`, `decimal`, `date`, `datetime`, `binary`, or `unknown`.

Unknown database types do not crash by default. They map to `unknown` and add a warning. Set
`fail_on_unknown_types=True` to reject them.

Duplicate output field names are rejected case-insensitively by default. Use explicit SQL aliases:

```sql
SELECT
    a.id AS patient_id,
    b.id AS order_id
FROM ...
```

## Security Boundary

Query field discovery executes the validated SELECT query using a restricted read-only database
connection.

It fetches only a very small number of rows for metadata purposes, but the database may still
perform substantial server-side work for complex queries.

Production report users must use minimum SELECT privileges, and report queries should be reviewed
and optimized.

The SQL validator does not replace database privileges. The discovery service does not permit write
SQL, multiple statements, string-interpolated parameters, sample row return values, full report data
fetching, local infile, or automatic dataset mutation.
