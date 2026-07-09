# Aggregate And System Fields

Aggregate and system fields are resolved by the core renderer and can be used in field bindings, text bindings, formulas, and conditional rules.

## Group Aggregates

Available inside Group Header, Detail rows with group context, and Group Footer:

- `group.value`
- `group.key`
- `group.field`
- `group.count`
- `group.sum.field`
- `group.avg.field`
- `group.min.field`
- `group.max.field`

Example:

```json
{
  "type": "field",
  "binding": "group.count",
  "band": "group_footer_results"
}
```

Invalid numeric values are ignored for numeric aggregates.

## Report Aggregates

Report aggregates run over array paths:

- `report.count.results`
- `report.sum.results.numeric_value`
- `report.avg.results.numeric_value`
- `report.min.results.numeric_value`
- `report.max.results.numeric_value`

Missing arrays resolve safely.

## Page And Date Fields

Available system fields:

- `page.number`: 1-based generated page number
- `page.index`: 0-based generated page index
- `page.total_pages`: total generated pages
- `page.count`: alias for total generated pages
- `date.today`
- `datetime.now`

Example formula:

```text
concat('Page ', page.number, ' of ', page.total_pages)
```

HTML preview and PDF export use the same page variables.
