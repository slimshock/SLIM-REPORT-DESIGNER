# Runtime Query Parameters

SLIM REPORT DESIGNER separates query parameter definitions from runtime values.
Definitions are report metadata: name, type, required state, label, and an optional
configured default. Runtime values are temporary inputs used for report execution.

They are not stored in the report template, browser storage, history, logs, or
credential configuration. The Designer keeps entered values only while the Report
Parameters dialog is open and clears them when it closes.

## Resolution

Values are resolved independently for each dataset. The precedence is:

1. Explicit user/runtime value
2. Application-provided value
3. Configured template default
4. `None` for an optional parameter
5. A missing-required error

Names are case-sensitive during resolution. Same-named parameters in separate
datasets never collide. Explicit `0` and `False` values override defaults.

Required `None` and blank strings are rejected. Optional `None` resolves to `None`.
For non-string parameters, blank browser input is treated as missing and may use a
configured default. Optional blank strings resolve to `None`; surrounding whitespace
in non-blank strings is preserved by default.

## Types

Supported types are `string`, `integer`, `float`, `decimal`, `boolean`, `date`,
`time`, and `datetime`.

- Integers reject booleans and decimal/scientific text.
- Floats and decimals reject NaN and infinity. Decimals remain exact Python
  `Decimal` values and use `.` as the separator.
- Booleans accept `True`, `False`, `1`, `0`, and case-insensitive `true`, `false`,
  `yes`, and `no` strings.
- Dates, times, and datetimes use ISO input. Time values are timezone-neutral.
  Datetimes preserve the supplied wall-clock or timezone information without an
  implicit conversion.
- The existing discovery converter intentionally accepts a datetime for a date or
  time parameter by selecting its date or time component.

Configured `Decimal`, date, time, and datetime defaults serialize as strings. At
runtime they pass through the trusted converter again. Unsupported objects and
non-finite defaults are rejected before a report can serialize successfully.

## Core API

```python
from slim_report_core import ReportRuntimeParameterService

service = ReportRuntimeParameterService()
schema = service.schema_for_report(report, dataset_ids=("daily_orders",))
resolved = service.resolve_report(
    report,
    values_by_dataset={
        "daily_orders": {
            "date_from": "2026-01-01",
            "date_to": "2026-01-31",
        }
    },
    dataset_ids=("daily_orders",),
)
```

The resulting mapping is immutable and contains converted Python values. A host may
also pass application values to the resolver. These values remain runtime-only.

Parameter values are converted to trusted Python values and later passed to the
database driver through parameter binding. They are never inserted into SQL text.

## Designer And API

Query datasets expose a **Parameters** action in the Dataset Manager. The dialog
renders controls appropriate to each type, restores configured defaults, clears
temporary values, and validates through the core resolver. It does not modify the
report or undo history.

The Flask adapter provides report-template POST operations for schema retrieval and
validation. Values stay in the request body. Responses contain schema/default
metadata, safe field errors, or validation counts; they do not echo submitted or
converted values. These operations open no database connection and execute no SQL.

Sprint 7.11 validates and resolves runtime parameter values. Complete dataset
execution begins in Sprint 7.12.
