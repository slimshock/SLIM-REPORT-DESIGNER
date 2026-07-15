# Read-Only MySQL Dataset Execution

SLIM REPORT DESIGNER provides a bounded runtime for executing configured MySQL
query and reporting-view datasets. The runtime is framework-independent and returns
a closeable stream of immutable, dataset-scoped rows.

Sprint 7.12 does not connect live rows to the Designer canvas, HTML preview, PDF
output, grouping, or Detail-band repetition. That renderer integration begins in
Sprint 7.13.

## Execution Lifecycle

Before opening a connection, `DatasetExecutionService` resolves the dataset and data
source, verifies the MySQL execution capability, validates stored fields and options,
checks cancellation, and prepares the command.

For a custom query it then:

1. Revalidates the stored SQL with the MySQL `SQLValidator`.
2. Reconciles declared placeholders.
3. Resolves runtime values with `RuntimeParameterResolver`.
4. Converts named placeholders using the existing token-aware converter.
5. Passes converted Python values separately to PyMySQL.

Every custom dataset query is revalidated immediately before execution.

The MySQL provider also configures and verifies a read-only session. Production
deployments must still use a dedicated account with minimum SELECT privileges.

For a reporting view, the runtime structurally reapplies `MetadataAccessPolicy`,
quotes the configured schema, view, and explicit stored fields, and generates a
trusted internal `SELECT`. It does not use `SELECT *` or append user-provided SQL.

## Streaming And Schema Validation

The MySQL provider requests `pymysql.cursors.SSCursor`. Cursor description is
validated before the first row is fetched. Under the default strict policy, returned
columns must have the same count, order, and case-insensitive names as the stored
dataset fields. Stored casing is retained in row mappings. Schema drift requires an
explicit field refresh or rediscovery.

Dataset rows are fetched incrementally with an unbuffered cursor.

The runtime never calls `fetchall()` and does not retain the complete result set in
memory. It uses bounded `fetchmany()` calls and can expose rows individually or as
immutable `DatasetRowBatch` values.

The default policy limits execution to:

- 10,000 yielded rows
- 200 rows per batch
- 500 columns
- 30 seconds, additionally bounded by the data-source query timeout
- 1 MiB per cell
- 64 MiB of approximate yielded cell data

When the row limit is reached, one additional row is fetched as lookahead. That row
is never yielded. Its presence sets `summary.truncated=True`; a result ending exactly
at the limit is not marked truncated.

Accepted values include null, text, binary data, booleans, integers, finite floats,
finite decimals, and Python date/time values. `bytearray` and `memoryview` become
immutable `bytes`. Unknown objects and non-finite numbers are rejected by default.

## Timeout And Cancellation

Runtime timeout is applied through MySQL client socket timeout settings.

It limits how long the client waits for database I/O but does not guarantee immediate
server-side cancellation. The report data source is copied with the effective timeout;
the stored configuration is not changed.

`DatasetExecutionCancellationToken` is thread-safe. The stream checks it before
connection creation, before execution, and around every batch fetch. Cancelling also
closes the active cursor and connection as soon as practical. MySQL may continue work
briefly after the client connection closes.

## Resource And Data Lifecycle

Context-manager usage is the supported default. Normal completion, empty results,
truncation, cancellation, timeouts, schema errors, row errors, size limits, early loop
termination, and consumer exceptions all close the unbuffered cursor before the
provider-owned connection. Cleanup is idempotent.

Database rows and runtime parameter values are never stored in the report template.
They are also not placed in browser storage, Flask session, history, logs, or global
caches. Execution summaries contain counts, timing, truncation/cancellation state, and
safe warnings only.

## Programmatic Usage

```python
from slim_report_core import (
    DatasetExecutionOptions,
    DatasetExecutionService,
    RuntimeParameterResolver,
)

execution_service = DatasetExecutionService(
    provider_registry=registry,
    sql_validator=mysql_sql_validator,
    parameter_resolver=RuntimeParameterResolver(),
)

with execution_service.open_dataset(
    report,
    "daily_orders",
    parameter_values={
        "date_from": "2026-01-01",
        "date_to": "2026-01-31",
    },
    options=DatasetExecutionOptions(max_rows=1000, batch_size=100),
) as stream:
    for batch in stream.iter_batches():
        consume_batch(batch)

    summary = stream.summary()
```

Per-execution options may reduce policy limits but cannot increase them. Rows and
batches do not retain a connection or cursor. `summary()` reports the safe current
state before, during, or after iteration; truncation is definitive only after the
stream performs its row-limit lookahead.
