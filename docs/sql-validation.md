# SQL Validation

Sprint 7.2 provides a framework-agnostic SQL security engine in `slim_report_core`. MySQL is the
first supported dialect. Validation parses SQL in memory with `sqlglot`; it does not connect to a
database, inspect a schema, discover fields, or execute a query.

## Usage

```python
from slim_report_core import MySQLDialect, SQLValidator

validator = SQLValidator(
    dialect=MySQLDialect(),
)

result = validator.validate(
    """
    SELECT
        orderid,
        pname
    FROM report_patient_results
    WHERE orderdate BETWEEN :date_from AND :date_to
    """
)

print(result.parameters)
# ('date_from', 'date_to')
```

The result also contains the normalized SQL, the root statement (`SELECT` or `WITH`), the dialect
name, and any warnings produced by dataset validation.

## Supported SQL

The MySQL dialect accepts one read-only query rooted at either:

- `SELECT`
- `WITH ... SELECT ...`

CTEs and `UNION` queries are enabled by default and can be disabled with
`SQLValidationPolicy(allow_cte=False, allow_union=False)`. A policy also limits query length and
the number of unique named parameters.

The validator rejects:

- multiple statements, including two `SELECT` statements;
- all write, DDL, administrative, inspection, and execution statements;
- `FOR UPDATE`, `LOCK IN SHARE MODE`, `INTO OUTFILE`, `INTO DUMPFILE`, and `INTO @variable`;
- MySQL user variables (`@name`), system variables (`@@name`), and assignment operators (`:=`);
- `SLEEP`, `BENCHMARK`, `LOAD_FILE`, `GET_LOCK`, `RELEASE_LOCK`, `IS_FREE_LOCK`,
  `IS_USED_LOCK`, `MASTER_POS_WAIT`, and `SOURCE_POS_WAIT` calls;
- MySQL executable/version comments (`/*! ... */`), whose contents may be run by the server;
- malformed SQL and unsupported parameter styles.

Checks are case-insensitive and syntax-aware. SQL-looking text inside string literals, comments,
or quoted identifiers does not become an operation or a statement separator.

User-supplied report SQL may not read or assign MySQL user variables or system variables.
Internal provider queries used to verify connection state are trusted provider operations and are
not user report queries.

`SQLParser` keeps sqlglot token details behind the parser boundary and returns immutable,
library-neutral facts for user variables, system variables, and assignment syntax. The validator
does not use raw substring matching for these checks.

## Named Parameters

Only `:name` parameters are supported:

```sql
SELECT *
FROM report_patient_results
WHERE orderdate BETWEEN :date_from AND :date_to
  AND client_id = :client_id
```

Names begin with a letter or underscore and contain only letters, digits, and underscores. The
result reports each name once, preserving its first appearance. Positional `?`, `%s`, `%(name)s`,
`${name}`, and `{{name}}` placeholders are rejected. Applications must still bind values through
their database driver's parameter API; never interpolate values into SQL strings.

For a `ReportDataset`, use `validator.validate_dataset(dataset)`. Every SQL parameter must have a
matching dataset parameter declaration. Duplicate declarations are errors. Declared parameters
that are not referenced by the SQL are returned as warnings.

## Normalization

Normalization is deliberately minimal. It trims leading and trailing whitespace and removes one
trailing semicolon. It does not reformat SQL, change keyword case, change identifier case, reorder
clauses, or modify literals.

## Security Boundary

Validation is defense in depth, not a database authorization system. A parser cannot guarantee
that future database features, stored routines, permissions, or server configuration are harmless.
The MySQL account used to run report queries should therefore have only the required `SELECT`
privileges on an explicit set of reporting views or tables. It should not have write, DDL, file,
administrative, or broad schema privileges.

Keep query execution outside this validation package, bind all values, apply runtime timeouts and
row limits, and log rejected queries without logging secrets. SQL validation does not replace any
of those controls.
