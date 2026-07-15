# MySQL Data-Source Provider

See [Read-Only MySQL Dataset Execution](dataset-execution.md) for the bounded
unbuffered runtime used to execute configured report datasets.

Sprint 7.3 adds a framework-independent provider for opening and testing read-only MySQL-compatible
connections. It establishes connections, configures and verifies session state, performs a minimal
health check, captures safe metadata, and closes every resource. It does not execute report dataset
SQL, list database objects, inspect schemas, discover fields, or fetch preview rows.

> **Security warning:** The provider's read-only session configuration is a defense-in-depth
> measure. Production report connections must still use a dedicated database account with only the
> required `SELECT` privileges, preferably restricted to approved reporting views. SQL validation
> and session settings do not replace MySQL permission controls.

## Installation and Driver Decision

PyMySQL was selected because it is maintained, pure Python, compatible with Python 3.11, requires
no native Windows compiler, and supports MySQL and MariaDB. It is an optional core dependency:

```bash
pip install "slim-report-core[mysql]"
```

The dependency is constrained to `PyMySQL>=1.1,<2`. It is imported lazily and only inside the
MySQL provider package. Importing or using other `slim_report_core` features does not require the
driver. Calling the provider without the extra installed raises `MissingDriverError` with the
installation command; a raw `ModuleNotFoundError` does not escape.

## Configuration and Credentials

Use the existing Sprint 7.1 metadata models:

```python
from slim_report_core import MySQLConnectionConfig, ReportDataSource

config = MySQLConnectionConfig(
    host="localhost",
    port=3306,
    database="lis",
    username="report_user",
    password_ref="SLIM_REPORT_MYSQL_PASSWORD",
    charset="utf8mb4",
    connect_timeout=10,
)

data_source = ReportDataSource(
    id="main_mysql",
    name="Main MySQL",
    type="mysql",
    connection=config,
)
```

Password resolution preserves this order:

1. The runtime-only `password` value.
2. `password_ref` through a supplied `CredentialResolver`.
3. The default environment-variable resolver.
4. No password when no reference is configured.

An unresolved configured reference raises `CredentialUnavailableError`. Resolved passwords are
not cached globally, stored on the provider, serialized, logged, returned in test results, or
included in project exception messages. An absent password is passed to the driver as an empty
password, which supports intentionally passwordless development configurations without weakening
credential-reference validation.

The driver receives explicit keyword arguments with autocommit enabled. The provider does not pass
`local_infile`, `client_flag`, multi-statement flags, or any capability that enables `LOAD DATA
LOCAL` or multiple statements.

## Timeout Semantics

`connect_timeout` limits the time allowed to establish the MySQL connection. `query_timeout` is
passed to PyMySQL as both `read_timeout` and `write_timeout`, limiting how long the client waits for
database socket I/O while sending a query or waiting for its response. These generic timeout names
remain the only timeout fields stored in report JSON; PyMySQL-specific options are provider details.

Query timeout is enforced through client socket timeout settings. It limits how long the client
waits for database I/O but does not guarantee immediate server-side query cancellation. A MySQL
server may continue processing after the client disconnects. Complex reporting queries still need
review, appropriate indexes, and a dedicated SELECT-only account. Future provider work may add
server-side execution limits where supported.

## Provider Registry and Connection Testing

```python
from slim_report_core import DataSourceProviderRegistry, MySQLDataSourceProvider

registry = DataSourceProviderRegistry()
registry.register(MySQLDataSourceProvider())

provider = registry.get(data_source.type)
result = provider.test_connection(data_source)

print(result.success)
print(result.message)
print(result.server_version)
print(result.database)
print(result.read_only_verified)
```

Registry names are case-insensitive. Duplicate registration fails unless `replace=True` is passed,
and `available()` returns a sorted tuple.

`test_connection()` validates configuration, resolves credentials, opens a fresh connection,
configures read-only state, verifies it, runs `SELECT 1`, reads `DATABASE()`, captures the driver's
server-version string, and closes the connection. Expected server, authentication, timeout,
database, and read-only failures return `ConnectionTestResult(success=False, ...)` with a concise
safe message. Invalid configuration, an unresolved credential, an unsupported provider, and a
missing optional driver raise focused project exceptions.

The result never contains a connection, credentials, a raw driver exception, or a stack trace.
Elapsed time uses a monotonic clock.

## Context-Managed Connections

```python
with provider.connection(data_source) as connection:
    # Sprint 7.3 deliberately performs no dataset query here.
    pass
```

Every call owns a new connection. Read-only configuration and verification happen before the
connection is yielded. The connection closes after normal completion, caller exceptions, and setup
failures. Provider instances retain no live connection, cursor, or resolved credential, and no
pooling or implicit connection sharing is performed.

## Read-Only Enforcement and Policy

The provider issues:

```sql
SET SESSION TRANSACTION READ ONLY
```

It then checks `@@session.transaction_read_only`, falling back to `@@session.tx_read_only` for older
MySQL and MariaDB variants. It does not use `sql_safe_updates` as read-only protection. A state value
that reports the session is writable always fails.

The default immutable policy requires setup and verification:

```python
from slim_report_core import MySQLConnectionPolicy, MySQLDataSourceProvider

provider = MySQLDataSourceProvider(
    policy=MySQLConnectionPolicy(
        require_read_only_session=True,
        verify_read_only_session=True,
        allow_unverified_read_only=False,
    )
)
```

`allow_unverified_read_only=True` permits an explicit compatibility downgrade only when the server
cannot expose a supported verification variable. The result then remains
`read_only_verified=False` and includes a deterministic warning. It never converts evidence of a
writable session into success.

## Compatibility and Limitations

The connection and session commands are designed for MySQL 5.6 where supported, MySQL 5.7 and 8.x,
and MariaDB 10.x. The actual server version string is preserved, including a `-MariaDB` suffix. Some
older releases, proxies, or restricted accounts may reject the session command or expose neither
verification variable; the default policy fails closed in those cases.

Server behavior can also depend on engine, transaction, account, and proxy configuration. For that
reason, applications must combine:

- the Sprint 7.2 SQL validator;
- bound parameters rather than interpolation;
- this provider's verified read-only session;
- a dedicated account with least-privilege `SELECT` grants;
- application timeouts, row limits, and safe operational logging.

The provider-backed view discovery layer is documented in
[MySQL Read-Only Metadata Service](mysql-metadata-service.md).
