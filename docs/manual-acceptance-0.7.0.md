# Manual Acceptance: 0.7.0

## Environment

Run the four demo SQL files as an administrator, replace the reader password placeholder, copy
`.env.example` to ignored `.env`, and run `run_demo.ps1` or `run_demo.sh`. Confirm `/diagnostics` is
available only from loopback and contains no credential value, SQL, rows, or HTML.

## Designer workflow

Open the visible `Report Designer`, create a MySQL report, test the restricted source, import an
approved view, create the parameterized daily-orders dataset, discover fields, drag fields to the
Detail band, enter dates, and run Live Preview. Confirm base tables are absent and unsafe SQL never
reaches MySQL.

## Reopen and recovery

Save, close, and reopen both samples. Remove the credential environment variable and confirm editing
still works with an unresolved warning. Restore it and reconnect without changing template JSON.
Change a view field, confirm stale-field repair is offered, repair it, and save again.

## Output and state

Check empty, truncated, timeout, cancellation, and schema-mismatch paths. Confirm values are escaped,
the preview frame is sandboxed, responses are `no-store`, and preview does not modify dirty state,
history, saved templates, credentials, runtime values, rows, HTML, or execution summaries.
