# New MySQL Report Wizard

The Report Designer toolbar provides **New Report** (`Ctrl+N`) for creating a blank report or a MySQL-backed report. Opening the wizard does not alter the active report. When unsaved changes exist, the user must save, explicitly continue without saving, or cancel.

## Draft Lifecycle

Wizard navigation uses temporary in-memory state. Cancel preserves the active report, selection, history, and dirty state and clears password and temporary query-value controls. The active report is replaced only after the final core build, relationship validation, binding validation, and serialization check succeed.

Existing MySQL definitions use the **Import From Current Report** approach. The wizard copies the selected safe serialized definition into its draft. Resolved passwords are not copied. A new source is created through the existing Data Source Management API against the temporary draft, not the active report.

## Workflow

The wizard collects report information and pixel-based A4, Letter, Legal, or custom page settings. MySQL reports then configure a source and either:

- load and inspect an approved reporting view, or
- validate one read-only SELECT query, configure named parameters, provide temporary discovery values, and discover fields.

All discovered fields remain in the final dataset. Field selection controls only the starting canvas layout. Binary and unknown fields are retained as metadata but are not directly generated as text objects.

Temporary parameter values used for query field discovery are not stored in the report template. Resolved MySQL passwords are never stored in normal report JSON.

## Layouts

Blank layout creates the standard Page Header, Detail, and Page Footer bands. A MySQL blank layout includes the data source and complete dataset but establishes no Detail band context until a field is later bound.

Tabular layout uses printable page width and deterministic type/label weights to align static Page Header labels with Detail text objects. It generates one structured dataset-field binding per selected field and establishes the canonical Detail band dataset context. Narrow layouts require explicit **Create Anyway** confirmation and still remain inside page margins.

The New Report Wizard creates report configuration, dataset metadata, field bindings, and an initial canvas layout. It does not execute the complete dataset or display live database rows.
