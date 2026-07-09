# Data Fields

The Data Fields panel helps users find available data paths and bind report fields without memorizing the data structure.

Data metadata is optional. Old templates without `data.sample` or `data.fields` still work.

## `template.data.sample`

`data.sample` stores example render data inside a template. The designer can use it for sample rendering, field inference, and preview/export requests.

## `template.data.fields`

`data.fields` stores optional metadata for field paths:

- `path`
- `label`
- `type`
- `sample`

The designer can infer fields from sample data and can also preserve explicitly curated field metadata.

## Dot Paths

Examples:

- `patient.name`
- `order.id`
- `results.hgb`

## Array Paths

Examples:

- `results[]`
- `results[].test`
- `results[].value`

Array paths are useful for the Data Fields panel and for repeating Detail rows.

## Binding Picker

The binding picker uses field metadata and inferred sample paths to choose a binding for field objects. Field objects store the actual render binding in `binding`; `source_path` may be used as optional designer metadata.

## Sample Data Editor

The sample data editor lets users edit `template.data.sample` in the designer. This is useful for previewing templates without connecting a real application provider.

## Placeholder Mode vs Sample Data Mode

Placeholder mode shows bindings such as `patient.name` on the canvas.

Sample data mode resolves fields from `data.sample` so the canvas looks closer to preview/export output.

## Static Mode Behavior

In static mode, sample data and field metadata live in the JSON template and browser-local editing state. Import/export JSON is the persistence mechanism.

## Flask Preview/Export Data Resolution

In Flask mode, preview/export can use explicit request data, `template.data.sample`, or provider data registered in the Flask app. The adapter passes the resolved data to `slim_report_core`.

## Example

```json
{
  "data": {
    "sample": {
      "patient": {
        "name": "Juan Dela Cruz"
      },
      "results": [
        {
          "test": "WBC",
          "value": "7.1"
        }
      ]
    },
    "fields": [
      {
        "path": "patient.name",
        "label": "Patient Name",
        "type": "string",
        "sample": "Juan Dela Cruz"
      },
      {
        "path": "results[].test",
        "label": "Test",
        "type": "string",
        "sample": "WBC"
      }
    ]
  }
}
```
