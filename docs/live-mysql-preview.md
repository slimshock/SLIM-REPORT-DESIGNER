# Live MySQL Report Preview

Sprint 7.13 connects validated MySQL dataset execution to the existing HTML object renderer. It
is limited to one primary MySQL dataset and bound text objects in a Detail band.

## Runtime Path

1. The Designer resolves the dataset-bound Detail band. Reports without one keep the existing
   static preview behavior.
2. Query datasets with parameters use the existing Report Parameters dialog. View datasets and
   queries without parameters proceed directly.
3. `DatasetExecutionService` revalidates the stored SELECT or approved view, resolves temporary
   parameters, opens a read-only stream, and validates the returned schema.
4. `RuntimeReportRenderService` validates bindings before execution, consumes one row at a time,
   repeats fixed-height Detail content, and paginates above the footer.
5. Existing HTML object helpers render each object. The bounded document is displayed in an
   iframe sandboxed without script permission.

The framework-independent service can be reused by future database-driven PDF export. This
sprint does not add that export path.

## Dataset and Binding Rules

Primary dataset resolution uses an explicit preview dataset ID, the Detail-band dataset context,
then the sole report dataset. Multiple Detail datasets are rejected.

Structured dataset-field bindings are the source of truth during live preview.

Visible placeholders in the Designer are not parsed to resolve data. Bound text uses the current
row; unbound Detail objects repeat as static content. Missing fields, cross-dataset bindings,
unsupported object bindings, and stale schemas fail safely. Data-driven grouping is outside this
sprint.

## Pagination and Limits

Runtime rendering reuses page dimensions, orientation, bands, margins, object coordinates,
assets, CSS classes, conditional styling, and page-header/footer behavior. A Detail instance is
not split across pages. A Detail row taller than the printable area is rejected.

Designer preview uses stricter row, page, object, timeout, and output limits than full runtime
execution. Defaults are 500 rows, 100 pages, 100,000 objects, 30 seconds, and 20 MiB of HTML.
Truncation is a preview-only warning. Empty results retain static page content and show a message
outside the report page.

## Cancellation

Each request owns a `DatasetExecutionCancellationToken`. Flask stores only the token, owner key,
report key, and start time in a short-lived thread-safe process-local registry. Cancel Preview
signals active resource cleanup, and the record is removed after every terminal state.

Cancellation closes client execution resources as soon as practical. MySQL may continue a
server-side query briefly after disconnect. Production hosts may replace the development
in-memory registry.

## Security and Persistence

All database values are treated as untrusted text and escaped before they are inserted into HTML
output. Newlines use the existing `white-space: pre-wrap` behavior. Responses use
`Cache-Control: no-store` and `Pragma: no-cache`. SQL, credentials, parameter values, rows, raw
driver exceptions, and complete HTML are not logged.

Live preview rows, runtime parameter values, preview HTML, execution summaries, and cancellation
state are never stored in the report template. They are also absent from browser storage, Flask
session, cookies, undo history, and asset storage. Closing preview clears the iframe and parameter
inputs. Preview does not mutate report geometry, bindings, fields, dirty state, or history.

Sprint 7.14 will address final persistence, credential-reference reconnect behavior, stale
dataset warnings, and safe report reopen workflows.
