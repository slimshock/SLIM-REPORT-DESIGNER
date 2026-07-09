# Advanced Table Designer

Sprint 6.5 keeps `type: "table"` as the only table object type and expands the schema around it. Existing templates that use `data_path`, `columns`, `header`, `row`, and `border` remain valid.

## Schema

Table objects accept both the original keys and LIS-friendly aliases:

- `data_path`, `dataSource`, `data_source`, or `binding`
- `autoHeight` or `auto_height`
- `showHeader`, `headerHeight`, and `rowHeight`
- `header`, `row`, `border`, and `grid`
- `headerStyle`, `bodyStyle`, and `sectionStyle`
- column `label`/`title`, `binding`/`field`, `fontSize`, `fontWeight`, and `wrap`
- `conditionalFormatting`

Example:

```json
{
  "id": "results_table",
  "type": "table",
  "dataSource": "results",
  "autoHeight": true,
  "showHeader": true,
  "headerHeight": 24,
  "rowHeight": 22,
  "columns": [
    { "id": "test_name", "title": "Test", "field": "test_name", "width": 150 },
    { "id": "result", "title": "Result", "field": "result", "width": 80, "align": "right" }
  ],
  "grid": { "showHorizontal": true, "showVertical": true },
  "conditionalFormatting": [
    {
      "column": "result",
      "when": "flag == 'HIGH'",
      "style": { "textColor": "#b91c1c", "fontWeight": "bold" }
    }
  ]
}
```

## Designer

The inspector includes data source selection, table presets, column add/delete/reorder controls, per-column binding and style controls, header/body style controls, border visibility, and horizontal/vertical grid toggles.

Use **Generate columns from data** after selecting a table data path to infer columns from `template.data.sample`. Presets provide common result-table layouts, including left/right hematology table presets.

## Rendering

HTML preview and PDF export resolve the same table schema:

- `dataSource` and column `field` aliases render the same as `data_path` and `binding`.
- `border.show` can hide the outer border while leaving grid lines visible.
- `grid.showHorizontal` and `grid.showVertical` draw row and column separators.
- `conditionalFormatting` applies style overrides per row and optionally per column.
- Rows with `row_type: "section"` or `type: "section"` render as full-width section rows.
- `rowHeight` and `headerHeight` are fixed rendered heights. Resizing the table object vertically does not stretch rows.
- With `autoHeight: true`, the rendered table height is `headerHeight + visibleRows * rowHeight`.
- With `autoHeight: false`, the object height is a clipping/blank container, but rows still keep `rowHeight`.

Conditional rules use the same safe expression evaluator as object conditional styles. Row fields are available directly, so rules such as `flag == 'HIGH'` work against each row.

## Limitations

Sprint 6.5 does not add merged cells, nested tables, grouped table objects, per-cell formulas, column spanning outside section rows, or automatic two-column flow. Build two-column LIS layouts with two table objects and split the data into left/right arrays before rendering.
