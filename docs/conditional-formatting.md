# Conditional Formatting

Conditional formatting lets an object change style, or hide, based on render data.

```json
{
  "id": "row_result",
  "type": "field",
  "binding": "result",
  "conditions": [
    {
      "id": "high",
      "enabled": true,
      "condition": "flag == 'H'",
      "style": {
        "color": "#dc2626",
        "bold": true,
        "background_color": "#fee2e2"
      }
    }
  ]
}
```

## Condition Syntax

Conditions use the same safe formula evaluator as computed fields. Useful examples:

```text
flag == 'H'
flag == 'L'
numeric_value > 10
patient.sex == 'F'
group.count > 5
contains(result, '+')
```

Invalid conditions evaluate as false and do not crash preview or PDF export.

## Style Merging

Rules are evaluated in order. When multiple rules match, later style keys override earlier keys while preserving keys that are not overwritten.

Supported style overrides include text color, background color, bold, italic, underline, borders, stroke color, and barcode/QR foreground color depending on object type.

## Hide Action

Use `action: "hide"` to suppress an object when a condition is true:

```json
{
  "condition": "default(result, '') == ''",
  "action": "hide"
}
```

This is useful for LIS abnormal flags, manual review labels, and blank optional fields.
