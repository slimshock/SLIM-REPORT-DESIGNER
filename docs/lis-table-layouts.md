# LIS Table Layouts

Use the existing Table object for LIS result grids. For dense layouts such as CBC or hematology reports, place two table objects side by side and bind each table to a separate array.

## Two-Column Hematology

The sample template at `examples/lis_templates/lab_result_hematology_two_column.json` uses:

- `left_table` bound to `left_results`
- `right_table` bound to `right_results`
- shared columns for `test_name`, `result`, `unit`, `normal_values`, and `flag`
- `conditionalFormatting` for `HIGH`, `LOW`, and `CRITICAL` flags
- `row_type: "section"` rows in the right table for manual grouping

Recommended data shape:

```json
{
  "left_results": [
    {
      "test_name": "Hemoglobin",
      "result": "180",
      "unit": "g/L",
      "normal_values": "135 - 175",
      "flag": "HIGH"
    }
  ],
  "right_results": [
    { "row_type": "section", "label": "Differential Count" },
    {
      "test_name": "Neutrophils",
      "result": "0.82",
      "unit": "ratio",
      "normal_values": "0.50 - 0.70",
      "flag": "HIGH"
    }
  ]
}
```

## Layout Guidance

Keep both table objects aligned on the same `y` coordinate and use equal heights when the report should read as one grid. Use a department bar or text object above both tables instead of nesting headers inside the tables.

Split data in the LIS integration layer. The renderer does not automatically flow one long array into two columns in Sprint 6.5.

For section labels, add rows with `row_type: "section"` and `label`. The renderer uses `sectionStyle` and spans the row across all configured columns.
