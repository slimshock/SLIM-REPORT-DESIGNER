# Designer Dataset Fields and Bindings

Sprint 7.9 connects stored MySQL dataset field metadata to the Report Designer canvas. The Fields panel reads only `report.datasets` and each dataset's stored `fields`; opening, searching, or expanding the panel does not connect to MySQL or execute SQL.

## Fields Panel

The existing Fields tab lists datasets in report order and fields in stored field order. Dataset rows show a safe source summary, field count, and parameter count without showing SQL, parameter values, credentials, or database rows.

The panel supports:

- client-side dataset, field, and normalized-type search
- temporary expand and collapse state
- disabled direct insertion for `binary` and `unknown` fields
- drag to a report band using `application/x-slim-report-dataset-field`
- double-click, Enter, Space, or the **Insert Field** button
- explicit Data Sources and Datasets actions for empty configurations

Every drop payload is treated as untrusted. The Designer resolves the dataset and exact-cased field name again from the active report before changing report state.

## Binding Schema

Text objects use one canonical root-level binding:

```json
{
  "dataBinding": {
    "type": "datasetField",
    "datasetId": "patient_results",
    "field": "patient_name"
  }
}
```

`datasetId` is the stable authoritative dataset reference. Field matching is exact and case-sensitive. The binding is not duplicated in `properties`. The existing legacy expression `binding` remains supported separately for older field, table, barcode, and QR workflows.

A band that contains structured bindings stores one dataset context:

```json
{
  "dataBinding": {
    "datasetId": "patient_results"
  }
}
```

The first structured binding establishes the band context. Later bindings in that band must use the same dataset. Moving a bound object to another band follows the same rule. Clearing or deleting the final structured binding clears the now-unused band context.

## Canvas and Inspector

A valid field insertion creates one normal text object, applies type-appropriate width and alignment, preserves the pointer position within the target band, selects the object, marks the report dirty, and adds one undo entry.

The text inspector exposes Dataset, Field, binding status, and Clear Binding controls. Binding metadata remains authoritative when visible text or styling changes. Clear Binding preserves the current placeholder as static text.

A visible placeholder such as `{{patient_results.patient_name}}` is used only for Designer display. The structured dataset-field binding stored in the report template is authoritative. Runtime execution must not depend on parsing the placeholder text.

## Broken References and Dependencies

Bindings survive save, reload, clone, copy, undo, and redo. Missing datasets and fields are preserved and shown as warnings so the user can repair them. Refreshing stored fields reports warnings when a bound field disappears or changes type; it does not delete objects or rewrite bindings.

Dataset removal is rejected while an object or band context references that dataset. Cascading data-source removal is also rejected when any dependent dataset is bound.

## Scope

Sprint 7.9 stores and edits dataset-field bindings. It does not execute datasets or display live database row values. It also does not store runtime parameter values, passwords, resolved credentials, connections, cursor state, field search text, expansion state, or drag state.
