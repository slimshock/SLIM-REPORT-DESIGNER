# Release Notes: 0.7.0

Version 0.7.0 completes the first MySQL reporting milestone. Reports can define a credential-safe
MySQL data source, import approved reporting views, or use one validated read-only SELECT query with
named parameters. The Designer now includes Data Sources, Datasets, Fields, canvas binding, and a
New Report Wizard.

Runtime input is converted by declared parameter type and bound through the driver. Dataset rows are
streamed with row, time, page, cell, and output limits. Live HTML preview repeats the Detail band,
escapes database values, uses a sandboxed frame, supports cancellation, and returns `no-store`.

Saved templates contain `passwordRef`, never a password. Reopen remains editable when a credential
is unavailable and reports can reconnect without rewriting the template. This release also adds a
self-contained MySQL demo, safe error codes, security regression checks, wheel verification, and
clean-install smoke tooling.

Database migrations, non-MySQL providers, subreports, and production migration ownership are not
included.
