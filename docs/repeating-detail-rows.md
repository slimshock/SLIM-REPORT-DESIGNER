# Repeating Detail Rows

Repeating Detail rows let one Detail band render once per item in an array.

This feature is useful for lab result rows, invoice lines, itemized receipts, and other simple repeated record layouts.

## Repeat Settings

Repeating is configured on the Detail band:

```json
{
  "id": "detail",
  "type": "detail",
  "name": "Detail",
  "repeat": {
    "enabled": true,
    "data_path": "results",
    "row_height": 24,
    "preview_rows": 20,
    "empty_message": "No records"
  }
}
```

Settings:

- `data_path`: array path in render data
- `row_height`: vertical offset between repeated rows
- `preview_rows`: number of sample rows shown by the designer
- `empty_message`: message shown when no records exist

Only Detail band repeating is supported in this sprint.

## Row-Relative Bindings

When a Detail band repeats over `results`, field bindings inside that band can resolve against the current row.

- `test` resolves against the current row.
- `results[].test` resolves against the current row when repeating over `results`.
- `results[0].test` resolves as an explicit global path.

Example row data:

```json
{
  "results": [
    {"test": "WBC", "value": "7.1"},
    {"test": "RBC", "value": "5.0"}
  ]
}
```

A field with `"binding": "test"` renders `WBC` in the first row and `RBC` in the second row.

## Canvas Repeated Sample Preview

The designer can use `data.sample` and `preview_rows` to show repeated rows on the canvas while editing.

## HTML Preview Behavior

HTML preview repeats Detail-band objects for each row found at `data_path`. It offsets repeated objects by `row_height`.

## PDF Export Behavior

PDF export uses the same row data and row-relative binding behavior as HTML preview.

## Current Limitations

- Full multi-page overflow/pagination is not implemented yet.
- Group headers/footers are not implemented yet.
- A full table component is a separate future feature.
- Only Detail band repeating is supported in this sprint.
