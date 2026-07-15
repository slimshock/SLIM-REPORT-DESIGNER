# Safe Error Codes

Flask APIs expose a stable object with `code`, localizable `message`, and `details`. They never copy
raw exception text, class names, SQL, parameter values, rows, credentials, HTML, or stack traces.
Clients must branch on `code`, not message text.

| Category | Codes |
| --- | --- |
| Data source | `data_source_invalid`, `data_source_not_found`, `credential_unavailable`, `driver_missing`, `authentication_failed`, `database_unavailable`, `data_source_timeout`, `read_only_failed` |
| Metadata | `metadata_access_denied`, `metadata_unavailable`, `metadata_limit_exceeded`, `view_not_found`, `invalid_identifier` |
| SQL | `sql_invalid`, `sql_unsafe`, `sql_multiple_statements`, `sql_invalid_parameter_style` |
| Dataset | `dataset_not_found`, `dataset_discovery_failed`, `dataset_schema_mismatch`, `dataset_limit_exceeded`, `dataset_cancelled`, `dataset_timeout`, `dataset_not_executable`, `dataset_provider_unavailable` |
| Binding | `binding_missing_field`, `binding_conflict` |
| Preview | `preview_not_ready`, `preview_cancelled`, `preview_timeout`, `preview_output_limit`, `preview_failed` |
| Persistence | `template_invalid`, `template_future_version`, `template_not_found`, `template_storage_error` |
| Assets/access | `asset_not_found`, `invalid_asset_id`, `asset_forbidden`, `unsupported_asset_type`, `asset_storage_error`, `forbidden` |

Unknown exceptions map to `server_error` with HTTP 500. Validation failures use HTTP 400, missing
resources 404, cancellation 409, permission failures 403, unavailable dependencies/services 503,
and timeouts 504.
