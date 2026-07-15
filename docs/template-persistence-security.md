# Template Persistence and Safe Reopen

MySQL report templates persist connection configuration, `passwordRef`, datasets, parameter
definitions, discovered fields, bindings, and band dataset context. They never persist runtime
passwords, resolved environment values, runtime parameter values, database rows, preview HTML,
connection objects, cursors, connection-test state, or preview state.

`JSONSerializer` is the final persistence boundary. It removes legacy plaintext passwords during
load, records a safe migration warning on the loaded report, writes the canonical template version,
and rejects unsupported future major versions. `inspect_template_security(mapping)` reports unsafe
JSON paths without reading or returning the values. `create_persistable_report_snapshot(report)`
creates a detached secret-free model copy without changing the original report.

## Credential Resolution

Credential precedence is deterministic:

1. Runtime password held by the current adapter session.
2. Injected host `CredentialResolver`.
3. Exact environment key named by `passwordRef`.
4. An explicitly configured no-password connection.
5. A safe credential-unavailable error.

Runtime passwords in the Flask designer are stored in `InMemoryRuntimeCredentialStore`, keyed by a
browser-generated report-session key and data-source ID. Entries expire and are cleared when the
report is replaced, the credential mode changes, the user clears the password, or the browser
session reloads. This process-local store is a convenience for interactive sessions, not a system
credential vault.

```python
from slim_report_core import EnvironmentCredentialResolver
from slim_report_flask import SlimReportDesigner

designer = SlimReportDesigner(
    credential_resolver=EnvironmentCredentialResolver(),
)
```

Host callbacks may implement `resolve(reference, *, data_source=None)` and are never serialized.
Callbacks must return the secret or `None`; public errors and logs must not include the secret or
raw callback exception.

## Reopen and Save

`ReportTemplateReopenService` performs offline structural, credential, SQL, parameter, dataset, and
binding checks. It never connects to MySQL or executes SQL. Broken reports normally remain editable,
while execution-critical findings disable live preview. `ReportPreviewReadinessService` applies the
same fail-closed rules before runtime parameter collection.

`ReportSaveValidationService` blocks structural and secret-policy violations. Runtime readiness
problems such as an unresolved credential, missing fields, or a broken binding produce warnings and
can be saved for later repair. Save does not require a reachable database.

Field freshness is always explicit. View checks inspect approved metadata and query checks reuse
bounded field discovery. `DatasetFreshnessService` compares stored and discovered fields without
mutation; the Designer applies changes only after confirmation and preserves broken binding metadata
for repair.
