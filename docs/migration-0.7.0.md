# Migration to 0.7.0

Package version 0.7.0 does not change the report template schema version. Existing static reports
continue to load.

1. Upgrade the coordinated `slim-report-core`, `slim-report-designer-ui`, and `slim-report-flask`
   distributions together.
2. Replace any persisted `connection.password` field with a `connection.passwordRef` whose value is
   an application-owned credential key.
3. Configure that key through `EnvironmentCredentialResolver` or an application resolver at runtime.
4. Restrict database accounts to `SELECT` on approved views and verify read-only session support.
5. Reopen templates and repair stale dataset fields before live preview.

Flask APIs now return stable safe error objects and no longer include raw exception messages or class
names. Clients should branch on `error.code`, not message text. Runtime parameter values, rows,
preview HTML, and execution summaries must not be copied into report JSON or browser history.
