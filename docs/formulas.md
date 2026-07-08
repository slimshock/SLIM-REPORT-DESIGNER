# Formulas

Field objects can use safe computed formulas by setting `formula_mode` to `true`.

```json
{
  "id": "computed_result",
  "type": "field",
  "formula_mode": true,
  "formula": "concat(result, ' ', unit)",
  "band": "detail"
}
```

If a formula fails and a binding exists, the renderer can fall back to the binding. If no binding exists, the field renders empty.

## Common Examples

```text
concat(result, ' ', unit)
if(flag == 'H', 'HIGH', 'NORMAL')
number(numeric_value, 2)
default('', 'N/A')
upper(patient.name)
lower(patient.name)
trim(patient.name)
numeric_value * 2
concat('Page ', page.number, ' of ', page.total_pages)
```

## Context

Formulas can resolve:

- ordinary data paths such as `patient.name`
- row-relative fields such as `result`, `unit`, and `flag`
- group fields such as `group.count`
- report aggregates such as `report.count.results`
- system variables such as `page.number`

## Safety

The formula evaluator uses a strict AST whitelist. Python `eval`, `exec`, imports, list/dict construction, attribute access, and arbitrary calls are not allowed. Invalid or unsafe formulas return an error result instead of executing.

Preview and PDF export should not crash because of a bad formula.
