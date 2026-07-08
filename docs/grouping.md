# Grouping

Grouping lets repeated Detail rows be organized by a field such as `section`, `department`, or `category`.

The common band sequence is:

- `page_header`
- `group_header`
- `detail`
- `group_footer`
- `page_footer`

Object coordinates remain page-absolute. The `band` field tells the renderer which region owns the object.

## Group Header

```json
{
  "id": "group_header_results",
  "type": "group_header",
  "y": 100,
  "height": 32,
  "group": {
    "id": "results_section",
    "data_path": "results",
    "field": "section",
    "sort": "none"
  }
}
```

`group.value` and `group.key` resolve to the current group value. For example, if rows are grouped by `section`, the header can render `HEMATOLOGY` or `CHEMISTRY`.

## Group Footer

Group Footer bands can render totals for the current group:

- `group.count`
- `group.sum.numeric_value`
- `group.avg.numeric_value`
- `group.min.numeric_value`
- `group.max.numeric_value`

The footer uses the same group context as the header.

## Missing Values

Rows with a missing group field are placed into an empty-string group. Missing arrays and missing aggregate fields resolve safely rather than crashing.

## Current Limits

Grouping is intended for straightforward repeated rows. Advanced group pagination controls, keep-together rules, and nested groups are future work.
